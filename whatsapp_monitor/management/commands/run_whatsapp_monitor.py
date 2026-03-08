"""
Django management command: python manage.py run_whatsapp_monitor

Launches a persistent Chromium session pointed at WhatsApp Web,
opens the configured group, and polls for new messages every 30 s.
Valid strike reports are parsed and saved to StrikeReport.

First run: a QR code will appear in the terminal — scan it with your phone.
Subsequent runs reuse the saved session (no QR needed).

Settings (in .env / Django settings):
    WHATSAPP_GROUP   — exact display name of the target group
    WHATSAPP_SESSION — path to store the browser session
                       (default: <BASE_DIR>/whatsapp_session)
"""
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.conf import settings

from whatsapp_monitor.models import StrikeReport
from whatsapp_monitor.parser import parse_report

logger = logging.getLogger(__name__)

# How often to check for new messages (seconds)
POLL_INTERVAL = 30
# How long to wait for WhatsApp Web to load after navigation (ms)
PAGE_TIMEOUT  = 60_000


class Command(BaseCommand):
    help = 'Monitor a WhatsApp group and save strike reports to the DB.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group',
            default=getattr(settings, 'WHATSAPP_GROUP', ''),
            help='Exact group display name to monitor.',
        )
        parser.add_argument(
            '--session-dir',
            default=str(
                Path(getattr(settings, 'BASE_DIR', '.')) / 'whatsapp_session'
            ),
            help='Directory for persistent browser session.',
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            default=True,
            help='Run Chromium in headless mode (default: True).',
        )

    def handle(self, *args, **options):
        group_name  = options['group']
        session_dir = options['session_dir']

        if not group_name:
            self.stderr.write(self.style.ERROR(
                'Set WHATSAPP_GROUP in settings/.env or pass --group'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Starting WhatsApp monitor → group: "{group_name}"'
        ))
        self.stdout.write(f'Session directory: {session_dir}')

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'playwright is not installed. Run: pip install playwright && '
                'playwright install chromium'
            ))
            return

        with sync_playwright() as pw:
            self._run(pw, group_name, session_dir, options['headless'])

    # ------------------------------------------------------------------ #

    def _run(self, pw, group_name, session_dir, headless):
        Path(session_dir).mkdir(parents=True, exist_ok=True)

        ctx = pw.chromium.launch_persistent_context(
            session_dir,
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--mute-audio',
            ],
            viewport={'width': 1280, 'height': 900},
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            self._open_whatsapp(page)
            self._open_group(page, group_name)
            self._poll_loop(page, group_name)
        except KeyboardInterrupt:
            self.stdout.write('\nStopped by user.')
        except Exception as exc:
            logger.exception('Fatal error in WhatsApp monitor: %s', exc)
            self.stderr.write(self.style.ERROR(str(exc)))
        finally:
            ctx.close()

    def _open_whatsapp(self, page):
        self.stdout.write('Opening WhatsApp Web …')
        page.goto('https://web.whatsapp.com', wait_until='domcontentloaded')

        # Already logged in?
        try:
            page.wait_for_selector('[data-testid="chat-list"]', timeout=8_000)
            self.stdout.write(self.style.SUCCESS('Session restored — no QR needed.'))
            return
        except Exception:
            pass

        # Need QR scan
        self.stdout.write(self.style.WARNING(
            'Scan the QR code in the browser window (you have 3 minutes) …'
        ))
        page.wait_for_selector('[data-testid="chat-list"]', timeout=180_000)
        self.stdout.write(self.style.SUCCESS('Logged in!'))

    def _open_group(self, page, group_name):
        self.stdout.write(f'Opening group "{group_name}" …')

        # Click the search box
        page.click('[data-testid="search"]')
        page.fill('[data-testid="search"] input', group_name)
        time.sleep(1.5)

        # Click the first result matching the exact title
        chat = page.locator(f'[title="{group_name}"]').first
        chat.wait_for(timeout=10_000)
        chat.click()

        # Wait for message list to appear
        page.wait_for_selector('[data-testid="msg-container"]', timeout=15_000)
        self.stdout.write(self.style.SUCCESS(f'Opened group "{group_name}".'))

    def _poll_loop(self, page, group_name):
        seen: set[str] = set(
            StrikeReport.objects.values_list('whatsapp_msg_id', flat=True)
        )
        self.stdout.write(
            f'Polling every {POLL_INTERVAL}s. Already known: {len(seen)} messages.'
        )

        while True:
            try:
                self._check_messages(page, group_name, seen)
            except Exception as exc:
                logger.error('Error checking messages: %s', exc)
            time.sleep(POLL_INTERVAL)

    def _check_messages(self, page, group_name, seen):
        # All message containers in the current view
        containers = page.query_selector_all('[data-testid="msg-container"]')

        new_count = 0
        for container in containers:
            msg_id = container.get_attribute('data-id')
            if not msg_id or msg_id in seen:
                continue

            # Extract text
            text_el = container.query_selector('.copyable-text')
            if not text_el:
                continue

            raw_text = (text_el.inner_text() or '').strip()
            if not raw_text:
                continue

            # Extract timestamp + sender from data-pre-plain-text
            # format: "[HH:MM, DD.MM.YYYY] Sender: "
            pre = text_el.get_attribute('data-pre-plain-text') or ''
            received_at, sender_name = self._parse_pre_plain(pre)

            # Parse report
            parsed = parse_report(raw_text)
            parsed_ok = parsed is not None

            report = StrikeReport(
                whatsapp_msg_id = msg_id,
                raw_text        = raw_text,
                sender_name     = sender_name,
                group_name      = group_name,
                received_at     = received_at,
                parsed_ok       = parsed_ok,
            )
            if parsed:
                for field, value in parsed.items():
                    setattr(report, field, value)

            report.save()
            seen.add(msg_id)
            new_count += 1

            if parsed_ok:
                self.stdout.write(self.style.SUCCESS(
                    f'[+] {received_at:%d.%m %H:%M} {sender_name}: '
                    f'{report.pozyvnyi} / {report.target} → {report.get_result_display()}'
                ))

        if new_count:
            self.stdout.write(f'Saved {new_count} new message(s).')

    @staticmethod
    def _parse_pre_plain(pre: str):
        """Parse '[HH:MM, DD.MM.YYYY] Sender: ' into (datetime, sender)."""
        import re
        m = re.match(r'\[(\d{2}:\d{2}),\s*(\d{2}\.\d{2}\.\d{4})\]\s*([^:]+):', pre)
        if m:
            time_s, date_s, sender = m.group(1), m.group(2), m.group(3).strip()
            try:
                dt = datetime.strptime(f'{date_s} {time_s}', '%d.%m.%Y %H:%M')
                dt = dt.replace(tzinfo=timezone.utc)
                return dt, sender
            except ValueError:
                pass
        return datetime.now(tz=timezone.utc), ''
