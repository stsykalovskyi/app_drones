"""
Django management command: python manage.py run_whatsapp_setup

Opens a visible Chromium window with WhatsApp Web so you can scan the QR code
and authorise the session. Once the chat list is visible, the session is saved
to --session-dir and the command exits automatically.

Run this once on a new machine or after the session expires.
"""
from .base import WhatsAppBaseCommand, PAGE_TIMEOUT


class Command(WhatsAppBaseCommand):
    help = 'Interactive WhatsApp Web setup: scan QR code and save session.'

    def add_arguments(self, parser):
        self.add_base_arguments(parser)
        # Override default: show the browser window so the user can scan the QR
        parser.set_defaults(headless=False)

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

        self.stdout.write('Opening browser for WhatsApp Web authorisation …')
        self.stdout.write('Scan the QR code in the browser window.')

        with sync_playwright() as pw:
            ctx  = self._make_context(pw, session_dir, headless, chromium_path)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(PAGE_TIMEOUT)

            self.stdout.write('Waiting for WhatsApp Web to load (up to 3 min) …')
            page.goto('https://web.whatsapp.com', wait_until='domcontentloaded')

            COMBINED = (
                '[data-testid="chat-list"],'
                '#pane-side,'
                '[data-testid="conversation-panel-wrapper"],'
                'header[data-testid="chatlist-header"]'
            )
            try:
                page.wait_for_selector(COMBINED, timeout=180_000)
                self.stdout.write(self.style.SUCCESS(
                    'Authorised! Session saved to: ' + session_dir
                ))
                self.stdout.write('You can now run: python manage.py run_whatsapp_sender')
            except Exception:
                page.screenshot(path='/tmp/wa_setup.png')
                self.stderr.write(self.style.ERROR(
                    'Timed out waiting for chat list. Screenshot: /tmp/wa_setup.png'
                ))
            finally:
                ctx.close()
