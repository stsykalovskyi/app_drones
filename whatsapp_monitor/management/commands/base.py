"""
Shared browser logic for WhatsApp management commands.
"""
import os
import time
import logging
import shutil
from pathlib import Path

os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)

PAGE_TIMEOUT = 60_000   # ms


class WhatsAppBaseCommand(BaseCommand):
    """Base class providing shared Playwright/WhatsApp browser utilities."""

    def add_base_arguments(self, parser):
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
            help='Path to Chromium binary. Auto-detected if not set.',
        )

    @staticmethod
    def _find_playwright_chromium() -> str:
        import glob
        cache = Path.home() / '.cache' / 'ms-playwright'
        for pattern in (
            'chromium-*/chrome-linux64/chrome',
            'chromium-*/chrome-linux/chrome',
        ):
            matches = sorted(glob.glob(str(cache / pattern)), reverse=True)
            if matches:
                return matches[0]
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
        exe = chromium_path or self._find_playwright_chromium()
        if exe:
            kwargs['executable_path'] = exe
            self.stdout.write(f'Chromium: {exe}')
        return pw.chromium.launch_persistent_context(session_dir, **kwargs)

    def _open_whatsapp(self, page):
        self.stdout.write('Opening WhatsApp Web …')
        page.goto('https://web.whatsapp.com', wait_until='domcontentloaded')

        COMBINED = (
            '[data-testid="chat-list"],'
            '#pane-side,'
            '[data-testid="conversation-panel-wrapper"],'
            'header[data-testid="chatlist-header"]'
        )
        try:
            page.wait_for_selector(COMBINED, timeout=90_000)
            self.stdout.write(self.style.SUCCESS('Session restored — no QR needed.'))
            return
        except Exception:
            pass

        if page.query_selector('[data-ref]'):
            raise RuntimeError(
                'Not logged in. Run setup first:\n'
                '  python manage.py run_whatsapp_setup'
            )

        page.screenshot(path='/tmp/wa_state.png')
        raise RuntimeError('WhatsApp Web loaded but chat list not found. Screenshot: /tmp/wa_state.png')

    def _open_group(self, page, group_name):
        self.stdout.write(f'Opening group "{group_name}" …')

        SEARCH_SELECTORS = [
            '[data-testid="search"]',
            '[data-testid="search-input"]',
            'div[contenteditable="true"][title]',
            'div[role="textbox"]',
        ]
        search_clicked = False
        for sel in SEARCH_SELECTORS:
            try:
                page.wait_for_selector(sel, timeout=10_000)
                page.click(sel)
                search_clicked = True
                break
            except Exception:
                continue

        if not search_clicked:
            page.screenshot(path='/tmp/wa_state.png')
            raise RuntimeError('Search box not found. Screenshot: /tmp/wa_state.png')

        page.keyboard.type(group_name)
        time.sleep(2.5)

        chat = None
        for locator in (
            page.locator(f'[title="{group_name}"]'),
            page.locator(f'[title*="{group_name}"]'),
            page.locator(f'span:text-is("{group_name}")'),
            page.locator(f'span:has-text("{group_name}")'),
        ):
            try:
                locator.first.wait_for(timeout=4_000)
                chat = locator.first
                break
            except Exception:
                continue

        if chat is None:
            page.screenshot(path='/tmp/wa_state.png')
            raise RuntimeError(
                f'Group "{group_name}" not found. Screenshot: /tmp/wa_state.png'
            )

        chat.click()

        for sel in ('div[data-id]', '[data-testid="msg-container"]', 'div[role="row"]'):
            try:
                page.wait_for_selector(sel, timeout=15_000)
                self.stdout.write(self.style.SUCCESS(f'Opened group "{group_name}".'))
                return
            except Exception:
                continue

        self.stdout.write(self.style.WARNING(
            f'Opened group "{group_name}" but message list not confirmed.'))

    def _send_message(self, page, text: str):
        COMPOSE_SELECTORS = [
            '[data-testid="conversation-compose-box-input"]',
            '[data-testid="compose-box-input"]',
            'footer div[contenteditable="true"]',
            'div[contenteditable="true"][data-tab="10"]',
            'div[contenteditable="true"][spellcheck="true"]',
        ]
        box = None
        for sel in COMPOSE_SELECTORS:
            try:
                box = page.wait_for_selector(sel, timeout=2_000)
                break
            except Exception:
                continue

        if box is None:
            page.screenshot(path='/tmp/wa_compose.png')
            raise RuntimeError('Compose box not found. Screenshot: /tmp/wa_compose.png')

        box.click()
        time.sleep(0.3)
        # Split on newlines: type each line, use Shift+Enter between them.
        # Plain Enter would send the message immediately in WhatsApp Web.
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line:
                page.keyboard.type(line, delay=30)
            if i < len(lines) - 1:
                page.keyboard.press('Shift+Enter')
        time.sleep(0.3)
        page.keyboard.press('Enter')
        time.sleep(1.0)
        self.stdout.write(self.style.SUCCESS(f'Sent: {text!r}'))

    def _send_file(self, page, file_path: str, caption: str = '') -> bool:
        """Attach and send a local media file (video/image) via WhatsApp Web.

        Returns True if caption was included, False if skipped (caller should
        send text separately).

        Flow:
          1. Click attach button → submenu opens
          2. Intercept file chooser when submenu option is clicked; set file
          3. Wait for preview modal (confirmed by send icon appearing)
          4. Type caption in caption field (contenteditable outside footer)
          5. Click DIV[aria-label="Надіслати"] outside footer (confirmed selector)
          6. Wait for modal to close
        """
        # ── 1. Open attach menu ───────────────────────────────────────────────
        ATTACH_SELS = [
            'button[aria-label="Вкласти"]',       # Ukrainian (confirmed)
            'button[aria-label="Attach"]',          # English
            'span[data-icon="plus-rounded"]',       # icon fallback
            '[data-testid="clip"]',
        ]
        for sel in ATTACH_SELS:
            try:
                page.wait_for_selector(sel, timeout=5_000).click()
                break
            except Exception:
                continue
        else:
            page.screenshot(path='/mnt/f/wa_attach_fail.png')
            raise RuntimeError('Attach button not found. Screenshot: /mnt/f/wa_attach_fail.png')

        time.sleep(0.4)

        # ── 2. Select file via file-chooser interceptor ───────────────────────
        # Use expect_file_chooser so we intercept at the browser level regardless
        # of which submenu item or input element triggers the dialog.
        attached = False
        try:
            with page.expect_file_chooser(timeout=10_000) as fc_info:
                # Try known submenu labels for photos/videos
                PHOTO_LABELS = [
                    'Фото та відео', 'Photos & Videos',
                    'Медіафайли', 'Photo & video',
                ]
                clicked_submenu = False
                for label in PHOTO_LABELS:
                    try:
                        page.locator(f'[aria-label="{label}"]').first.click(timeout=2_000)
                        clicked_submenu = True
                        break
                    except Exception:
                        continue

                if not clicked_submenu:
                    # Fallback: click first file input in DOM
                    for sel in ('input[type="file"][accept*="video"]',
                                'input[type="file"][accept*="image"]',
                                'input[type="file"]'):
                        el = page.query_selector(sel)
                        if el:
                            page.evaluate('el => el.click()', el)
                            break

            fc_info.value.set_files(file_path)
            attached = True
        except Exception as e:
            logger.warning('File chooser interceptor failed: %s — trying set_input_files', e)

        # Fallback: set_input_files directly on whatever input is visible
        if not attached:
            for sel in ('input[type="file"][accept*="video"]',
                        'input[type="file"][accept*="image"]',
                        'input[type="file"]'):
                el = page.query_selector(sel)
                if el:
                    try:
                        el.set_input_files(file_path)
                        attached = True
                        break
                    except Exception:
                        continue

        if not attached:
            page.screenshot(path='/mnt/f/wa_attach_fail.png')
            raise RuntimeError('File input not found. Screenshot: /mnt/f/wa_attach_fail.png')

        # ── 3. Wait for preview modal ─────────────────────────────────────────
        # The media send icon appearing means the preview modal is ready.
        try:
            page.wait_for_function(
                """() => !!document.querySelector('[data-icon="wds-ic-send-filled"]')""",
                timeout=20_000,
            )
        except Exception:
            time.sleep(3)

        # ── 4. Type caption ───────────────────────────────────────────────────
        caption_sent = False
        if caption:
            # Caption input: contenteditable div NOT inside footer
            cap_el = None
            for loc in page.locator('div[contenteditable="true"]').all():
                try:
                    in_footer = loc.evaluate(
                        'el => !!document.querySelector("footer")?.contains(el)'
                    )
                    if not in_footer:
                        cap_el = loc
                        break
                except Exception:
                    continue

            if cap_el:
                try:
                    cap_el.click()
                    time.sleep(0.2)
                    lines = caption.split('\n')
                    for i, line in enumerate(lines):
                        if line:
                            page.keyboard.type(line, delay=20)
                        if i < len(lines) - 1:
                            page.keyboard.press('Shift+Enter')
                except Exception as e:
                    logger.warning('Failed to type caption: %s', e)
                    cap_el = None

            # ── 5. Click media send button ────────────────────────────────────
            # Confirmed: DIV[aria-label="Надіслати"] with data-icon="wds-ic-send-filled"
            # located OUTSIDE footer.
            send_clicked = False
            for label in ('Надіслати', 'Send'):
                locs = page.locator(f'[aria-label="{label}"]')
                for i in range(locs.count()):
                    loc = locs.nth(i)
                    try:
                        in_footer = loc.evaluate(
                            'el => !!document.querySelector("footer")?.contains(el)'
                        )
                        if not in_footer:
                            loc.click()
                            send_clicked = True
                            logger.info('Clicked send button #%d [aria-label="%s"]', i, label)
                            break
                    except Exception:
                        continue
                if send_clicked:
                    break

            if send_clicked:
                caption_sent = True
                # Wait for modal to close — confirms message was dispatched
                try:
                    page.wait_for_function(
                        """() => !document.querySelector('[data-icon="wds-ic-send-filled"]')""",
                        timeout=15_000,
                    )
                except Exception:
                    time.sleep(3)
            else:
                page.screenshot(path='/mnt/f/wa_send_fail.png')
                logger.warning('Send button not found. Screenshot: /mnt/f/wa_send_fail.png')

        # ── 6. Fallback: no caption — just find and click any send button ─────
        if not caption_sent:
            sent = False
            for label in ('Надіслати', 'Send'):
                locs = page.locator(f'[aria-label="{label}"]')
                for i in range(locs.count()):
                    loc = locs.nth(i)
                    try:
                        in_footer = loc.evaluate(
                            'el => !!document.querySelector("footer")?.contains(el)'
                        )
                        if not in_footer:
                            loc.click()
                            sent = True
                            break
                    except Exception:
                        continue
                if sent:
                    break

            if not sent:
                page.screenshot(path='/mnt/f/wa_send_fail.png')
                raise RuntimeError(
                    'Send button not found after attaching file. '
                    'Screenshot: /mnt/f/wa_send_fail.png'
                )
            time.sleep(3)

        self.stdout.write(self.style.SUCCESS(
            f'Sent file: {file_path!r}'
            + (' (with caption)' if caption_sent else ' (no caption)')
        ))
        return caption_sent
