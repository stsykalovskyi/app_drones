"""
Django management command: python manage.py run_whatsapp_sender

Persistent sender worker. Keeps one Chromium session alive and polls
the OutgoingMessage table every --poll-interval seconds.

The process is meant to run continuously in the background (screen/systemd).
It is started automatically on deploy if not already running.

Enqueue a message:
    python manage.py send_whatsapp --group "Майстерня" --message "Текст"
"""
import time
import logging
from datetime import datetime, timezone

from django.db import transaction

from .base import WhatsAppBaseCommand, PAGE_TIMEOUT
from whatsapp_monitor.models import OutgoingMessage

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class Command(WhatsAppBaseCommand):
    help = 'Persistent WhatsApp sender: polls OutgoingMessage queue and sends messages.'

    def add_arguments(self, parser):
        self.add_base_arguments(parser)
        parser.add_argument(
            '--poll-interval',
            type=int,
            default=5,
            metavar='SECONDS',
            help='Seconds between queue checks (default: 5).',
        )

    def handle(self, *args, **options):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'playwright is not installed. Run: pip install playwright'
            ))
            return

        session_dir   = options['session_dir']
        headless      = options['headless']
        chromium_path = options['chromium_path']
        poll_interval = options['poll_interval']

        self.stdout.write(self.style.SUCCESS(
            f'Starting WhatsApp sender (poll every {poll_interval}s) …'
        ))

        with sync_playwright() as pw:
            self._run_sender(pw, session_dir, headless, chromium_path, poll_interval)

    # ------------------------------------------------------------------ #

    def _run_sender(self, pw, session_dir, headless, chromium_path, poll_interval):
        ctx = self._make_context(pw, session_dir, headless, chromium_path)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            self._open_whatsapp(page)
        except RuntimeError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            ctx.close()
            return

        current_group = None
        self.stdout.write('Sender ready. Polling queue …')

        try:
            while True:
                msg = self._fetch_next(poll_interval)
                if msg is None:
                    continue

                self.stdout.write(
                    f'[#{msg.id}] → [{msg.group_name}] {msg.message_text[:80]}'
                )

                try:
                    if current_group != msg.group_name:
                        self._open_group(page, msg.group_name)
                        current_group = msg.group_name

                    self._send_message(page, msg.message_text)

                    msg.status  = OutgoingMessage.Status.SENT
                    msg.sent_at = datetime.now(tz=timezone.utc)
                    msg.save(update_fields=['status', 'sent_at'])
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Sent #{msg.id}'))

                except Exception as exc:
                    logger.error('Failed to send #%s: %s', msg.id, exc)
                    msg.retry_count += 1
                    msg.error = str(exc)
                    if msg.retry_count >= MAX_RETRIES:
                        msg.status = OutgoingMessage.Status.FAILED
                        self.stderr.write(self.style.ERROR(
                            f'  ✗ #{msg.id} failed after {MAX_RETRIES} retries: {exc}'
                        ))
                    else:
                        msg.status = OutgoingMessage.Status.PENDING
                        self.stdout.write(self.style.WARNING(
                            f'  ↺ #{msg.id} retry {msg.retry_count}/{MAX_RETRIES}: {exc}'
                        ))
                    msg.save(update_fields=['status', 'error', 'retry_count'])

                    # QR detected → session expired
                    if page.query_selector('[data-ref]'):
                        self.stderr.write(self.style.ERROR(
                            'Session expired (QR detected). Sleeping 60s …'
                        ))
                        time.sleep(60)
                        try:
                            self._open_whatsapp(page)
                            current_group = None
                        except Exception as e:
                            logger.error('Reconnect failed: %s', e)

        except KeyboardInterrupt:
            self.stdout.write('\nStopped by user.')
        except Exception as exc:
            logger.exception('Fatal error in WhatsApp sender: %s', exc)
            self.stderr.write(self.style.ERROR(str(exc)))
        finally:
            ctx.close()

    def _fetch_next(self, poll_interval: int):
        """Atomically claim the oldest pending message. Returns None if queue is empty."""
        try:
            with transaction.atomic():
                msg = (
                    OutgoingMessage.objects
                    .select_for_update(skip_locked=True)
                    .filter(status=OutgoingMessage.Status.PENDING)
                    .first()
                )
                if msg is None:
                    time.sleep(poll_interval)
                    return None
                msg.status = OutgoingMessage.Status.SENDING
                msg.save(update_fields=['status'])
                return msg
        except Exception as exc:
            logger.error('DB error: %s', exc)
            time.sleep(poll_interval)
            return None
