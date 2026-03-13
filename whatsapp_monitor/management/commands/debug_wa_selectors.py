"""
Temporary debug command.
Usage:
    python manage.py debug_wa_selectors [--group "GroupName"]

Opens the saved WhatsApp session, opens the group, then prints all
data-testid / data-icon / aria-label values in the footer compose area.
Delete this command after the attach-button selector is identified.
"""
import time
import json

from django.conf import settings

from .base import WhatsAppBaseCommand


class Command(WhatsAppBaseCommand):
    help = 'Debug: dump footer element selectors from WhatsApp Web.'

    def add_arguments(self, parser):
        self.add_base_arguments(parser)
        parser.add_argument('--group', default=settings.WHATSAPP_STRIKE_GROUP or 'Test')
        parser.set_defaults(headless=False)

    def handle(self, *args, **options):
        from playwright.sync_api import sync_playwright

        group = options['group']

        with sync_playwright() as pw:
            ctx  = self._make_context(pw, options['session_dir'], options['headless'], options['chromium_path'])
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            self._open_whatsapp(page)
            self._open_group(page, group)
            time.sleep(1)

            result = page.evaluate("""() => {
                const footer = document.querySelector('footer');
                if (!footer) return [{error: 'footer not found'}];
                const els = footer.querySelectorAll('[data-testid],[data-icon],[aria-label]');
                return Array.from(els).map(el => ({
                    tag:    el.tagName,
                    testid: el.getAttribute('data-testid'),
                    icon:   el.getAttribute('data-icon'),
                    aria:   el.getAttribute('aria-label'),
                    title:  el.getAttribute('title'),
                }));
            }""")

            self.stdout.write('\n=== FOOTER ELEMENTS ===')
            for el in result:
                self.stdout.write(json.dumps(el, ensure_ascii=False))

            page.screenshot(path='/mnt/f/wa_footer_debug.png')
            self.stdout.write('\nScreenshot: /mnt/f/wa_footer_debug.png')
            ctx.close()
