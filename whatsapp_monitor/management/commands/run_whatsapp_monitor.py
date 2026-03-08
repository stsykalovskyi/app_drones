"""
Django management command: python manage.py run_whatsapp_monitor

Launches a persistent Chromium session pointed at WhatsApp Web,
opens the configured group, and polls for new messages every 30 s.
Valid strike reports are parsed and saved to StrikeReport.

First run (authentication):
    python manage.py run_whatsapp_monitor --setup
    # saves QR screenshot to /tmp/wa_qr.png — download with scp and scan

Subsequent runs reuse the saved session (no QR needed):
    python manage.py run_whatsapp_monitor

Settings (in .env / Django settings):
    WHATSAPP_GROUP   — exact display name of the target group
    WHATSAPP_SESSION — path to store the browser session
                       (default: <BASE_DIR>/whatsapp_session)
"""
import time
import logging
import shutil
from pathlib import Path
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.conf import settings

from whatsapp_monitor.models import StrikeReport
from whatsapp_monitor.parser import parse_report

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30        # seconds between message checks
PAGE_TIMEOUT  = 60_000    # ms — page load timeout
QR_TIMEOUT    = 180_000   # ms — how long to wait for QR scan


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
        parser.add_argument(
            '--chromium-path',
            default='',
            help='Path to system Chromium/Chrome binary. '
                 'Auto-detected if not set (checks chromium-browser, chromium, google-chrome).',
        )
        parser.add_argument(
            '--setup',
            action='store_true',
            default=False,
            help='Auth-only mode: screenshot the QR code, wait for scan, save session, exit.',
        )
        parser.add_argument(
            '--qr-path',
            default='/tmp/wa_qr.png',
            help='Where to save the QR screenshot in --setup mode (default: /tmp/wa_qr.png).',
        )

    def handle(self, *args, **options):
        group_name  = options['group']
        session_dir = options['session_dir']
        setup_mode  = options['setup']

        if not group_name and not setup_mode:
            self.stderr.write(self.style.ERROR(
                'Set WHATSAPP_GROUP in settings/.env or pass --group'
            ))
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'playwright is not installed. Run: '
                'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pip install playwright'
            ))
            return

        # Use explicit --chromium-path if given; otherwise let Playwright use
        # its own bundled browser (installed via `playwright install chromium`).
        chromium_path = options['chromium_path']
        if chromium_path:
            self.stdout.write(f'Using explicit Chromium: {chromium_path}')
        else:
            self.stdout.write('Using Playwright bundled Chromium.')

        with sync_playwright() as pw:
            if setup_mode:
                self._run_setup(pw, session_dir, options['headless'],
                                chromium_path, options['qr_path'])
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'Starting WhatsApp monitor → group: "{group_name}"'
                ))
                self.stdout.write(f'Session directory: {session_dir}')
                self._run(pw, group_name, session_dir, options['headless'], chromium_path)

    # ------------------------------------------------------------------ #

    def _save_qr(self, page, qr_path: str) -> bool:
        """
        Extract QR token from data-ref attribute and render a clean PNG.
        Returns True on success, False if token not found.
        """
        try:
            el = page.query_selector('[data-ref]')
            if not el:
                return False
            token = el.get_attribute('data-ref')
            if not token:
                return False

            import qrcode as _qrcode
            img = _qrcode.make(token)
            img.save(qr_path)
            return True
        except Exception as exc:
            logger.debug('_save_qr failed: %s', exc)
            return False

    @staticmethod
    def _find_chromium():
        """Return path to the first system Chromium/Chrome binary found."""
        for name in ('chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable'):
            path = shutil.which(name)
            if path:
                return path
        return ''

    def _make_context(self, pw, session_dir, headless, chromium_path):
        Path(session_dir).mkdir(parents=True, exist_ok=True)
        kwargs = dict(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--mute-audio',
            ],
            viewport={'width': 1280, 'height': 900},
            user_agent=(
                'Mozilla/5.0 (X11; Linux x86_64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
        )
        if chromium_path:
            kwargs['executable_path'] = chromium_path
        return pw.chromium.launch_persistent_context(session_dir, **kwargs)

    # ------------------------------------------------------------------ #
    # Setup (auth) mode
    # ------------------------------------------------------------------ #

    def _run_setup(self, pw, session_dir, headless, chromium_path, qr_path):
        from playwright._impl._errors import TimeoutError as PlaywrightTimeout

        self.stdout.write(self.style.WARNING(
            '=== SETUP MODE: authenticating WhatsApp session ==='
        ))
        ctx = self._make_context(pw, session_dir, headless, chromium_path)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            page.goto('https://web.whatsapp.com', wait_until='domcontentloaded')

            # Already logged in?
            try:
                page.wait_for_selector('[data-testid="chat-list"]', timeout=8_000)
                self.stdout.write(self.style.SUCCESS(
                    'Already logged in — session is valid. No QR needed.'
                ))
                return
            except Exception:
                pass

            # Wait for the QR container with data-ref attribute (holds QR token)
            self.stdout.write('Waiting for QR code to render …')
            try:
                page.wait_for_selector('[data-ref]', timeout=25_000)
            except Exception:
                page.screenshot(path=qr_path)
                self.stderr.write(self.style.ERROR(
                    'QR container not found — page screenshot saved.\n'
                    f'Check: scp root@85.121.4.216:{qr_path} /mnt/f/wa_qr.png'
                ))
                return

            time.sleep(2)
            saved = self._save_qr(page, qr_path)
            if not saved:
                self.stderr.write(self.style.ERROR(
                    'Could not extract QR data. Check the screenshot.'
                ))
                return
            self.stdout.write(self.style.SUCCESS(f'QR saved to: {qr_path}'))

            self.stdout.write(
                f'\n  scp root@85.121.4.216:{qr_path} /mnt/f/wa_qr.png\n'
                '  Open the file and scan with WhatsApp → Linked Devices → Link a Device\n'
                '  The file is refreshed every 15 s — re-open it if the QR expired.\n'
            )
            self.stdout.write('Refreshing QR screenshot every 15 s for up to 3 minutes …')

            # Refresh QR screenshot every 10 s until logged in or timeout
            deadline = time.monotonic() + QR_TIMEOUT / 1000
            logged_in = False
            while time.monotonic() < deadline:
                # Check if login happened
                try:
                    page.wait_for_selector('[data-testid="chat-list"]', timeout=2_000)
                    logged_in = True
                    break
                except Exception:
                    pass

                # If QR expired, click the reload button
                try:
                    for reload_sel in (
                        '[data-testid="refresh-large-icon"]',
                        'span[data-icon="refresh-large"]',
                        'div[role="button"]',
                    ):
                        btn = page.query_selector(reload_sel)
                        if btn:
                            btn.click()
                            self.stdout.write('  QR expired — clicked reload')
                            time.sleep(3)
                            break
                except Exception:
                    pass

                # Regenerate QR from data-ref token
                if self._save_qr(page, qr_path):
                    self.stdout.write(f'  QR refreshed → {qr_path}')
                else:
                    self.stdout.write('  Could not read QR data, retrying…')

                time.sleep(10)

            if not logged_in:
                page.screenshot(path=qr_path)
                self.stderr.write(self.style.ERROR(
                    'Timed out — QR was not scanned within 3 minutes.\n'
                    'Run --setup again.'
                ))
                return

            self.stdout.write(self.style.SUCCESS(
                '\nLogged in! Session saved.\n'
                'Start the monitor:\n'
                '  screen -dmS wamon bash -c "cd /root/MyProjects/python/app_drones && '
                'source .venv/bin/activate && '
                'python manage.py run_whatsapp_monitor >> /var/log/wamon.log 2>&1"'
            ))
        except KeyboardInterrupt:
            self.stdout.write('\nSetup cancelled.')
        except Exception as exc:
            logger.exception('Unexpected setup error: %s', exc)
            try:
                page.screenshot(path=qr_path)
                self.stderr.write(self.style.ERROR(
                    f'Unexpected error: {exc}\n'
                    f'Page screenshot saved to {qr_path}'
                ))
            except Exception:
                self.stderr.write(self.style.ERROR(f'Unexpected error: {exc}'))
        finally:
            ctx.close()

    # ------------------------------------------------------------------ #
    # Normal monitor mode
    # ------------------------------------------------------------------ #

    def _run(self, pw, group_name, session_dir, headless, chromium_path=''):
        ctx = self._make_context(pw, session_dir, headless, chromium_path)
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

        try:
            page.wait_for_selector('[data-testid="chat-list"]', timeout=8_000)
            self.stdout.write(self.style.SUCCESS('Session restored — no QR needed.'))
            return
        except Exception:
            pass

        self.stderr.write(self.style.ERROR(
            'Not logged in. Run first:\n'
            '  python manage.py run_whatsapp_monitor --setup'
        ))
        raise RuntimeError('WhatsApp session not authenticated. Run --setup first.')

    def _open_group(self, page, group_name):
        self.stdout.write(f'Opening group "{group_name}" …')

        page.click('[data-testid="search"]')
        page.fill('[data-testid="search"] input', group_name)
        time.sleep(1.5)

        chat = page.locator(f'[title="{group_name}"]').first
        chat.wait_for(timeout=10_000)
        chat.click()

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
        containers = page.query_selector_all('[data-testid="msg-container"]')

        new_count = 0
        for container in containers:
            msg_id = container.get_attribute('data-id')
            if not msg_id or msg_id in seen:
                continue

            text_el = container.query_selector('.copyable-text')
            if not text_el:
                continue

            raw_text = (text_el.inner_text() or '').strip()
            if not raw_text:
                continue

            pre = text_el.get_attribute('data-pre-plain-text') or ''
            received_at, sender_name = self._parse_pre_plain(pre)

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
