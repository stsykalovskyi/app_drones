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

        Returns True if caption was successfully included, False if it was skipped
        (WhatsApp UI changed or caption input not found). The caller should send
        the text as a separate message when False is returned.
        """
        FILE_INPUT_SELS = [
            'input[type="file"][accept*="video"]',
            'input[type="file"][accept*="image"]',
            'input[type="file"]',
        ]

        # Strategy 1: set file directly on hidden input — works if WhatsApp keeps
        # the input in DOM without needing to open the attach menu first.
        attached = False
        for sel in FILE_INPUT_SELS:
            el = page.query_selector(sel)
            if el:
                try:
                    el.set_input_files(file_path)
                    attached = True
                    break
                except Exception:
                    continue

        # Strategy 2: click attach button to reveal the input, then set file.
        if not attached:
            CLIP_SELS = [
                # Ukrainian UI (confirmed via debug_wa_selectors)
                'button[aria-label="Вкласти"]',
                'span[data-icon="plus-rounded"]',
                # English UI fallbacks
                'button[aria-label="Attach"]',
                'button[aria-label*="ttach"]',
                # Legacy data-testid (older WhatsApp versions)
                '[data-testid="clip"]',
                '[data-testid="attach-media"]',
                'span[data-icon="clip"]',
                'span[data-icon="attach-media"]',
                'span[data-icon="plus"]',
            ]
            clip_clicked = False
            for sel in CLIP_SELS:
                try:
                    page.wait_for_selector(sel, timeout=3_000).click()
                    clip_clicked = True
                    break
                except Exception:
                    continue

            if clip_clicked:
                time.sleep(0.5)
                # Try file-chooser interception first
                try:
                    with page.expect_file_chooser(timeout=6_000) as fc_info:
                        for sel in FILE_INPUT_SELS:
                            el = page.query_selector(sel)
                            if el:
                                page.evaluate('el => el.click()', el)
                                break
                    fc_info.value.set_files(file_path)
                    attached = True
                except Exception:
                    pass

                if not attached:
                    for sel in FILE_INPUT_SELS:
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

        # 3. Wait for preview — caption input is the most reliable signal
        #    that the preview is fully rendered and ready for interaction.
        CAPTION_SELS = [
            '[data-testid="media-caption-input"]',
            'div[contenteditable="true"][data-tab]',  # fallback if testid changes
        ]
        caption_el = None
        for sel in CAPTION_SELS:
            try:
                caption_el = page.wait_for_selector(sel, state='visible', timeout=20_000)
                break
            except Exception:
                continue

        if caption_el is None:
            # Caption input not found — WhatsApp UI may have changed.
            # Fall back to a short sleep so preview at least partially loads.
            logger.warning('Caption input not found — sending file without caption')
            time.sleep(3)

        # 4. Type caption and send by pressing Enter while caption field is focused.
        # Enter in the media-preview caption field sends the file+caption together.
        # This avoids the ambiguity of finding the correct Send button in the modal
        # (the compose-box send button is also in the DOM at the same time).
        caption_sent = False
        if caption and caption_el is not None:
            try:
                caption_el.click()
                time.sleep(0.2)
                cap_lines = caption.split('\n')
                for i, line in enumerate(cap_lines):
                    if line:
                        page.keyboard.type(line, delay=20)
                    if i < len(cap_lines) - 1:
                        page.keyboard.press('Shift+Enter')
                # Enter while focused on caption field sends the media message
                page.keyboard.press('Enter')
                # Verify modal closed — if it stays open the file was not sent
                modal_closed = False
                try:
                    page.wait_for_selector(
                        '[data-testid="media-caption-input"]',
                        state='detached', timeout=10_000,
                    )
                    modal_closed = True
                except Exception:
                    pass

                if modal_closed:
                    caption_sent = True
                else:
                    page.screenshot(path='/mnt/f/wa_after_enter.png')
                    logger.warning(
                        'Modal still open after Enter — file may be too large or '
                        'WhatsApp rejected it. Screenshot: /mnt/f/wa_after_enter.png'
                    )
            except Exception as e:
                logger.warning('Failed to type/send caption: %s', e)

        # 5. If caption send failed — click Send button in media preview modal.
        # The green circular Send button is OUTSIDE the footer (footer = compose area).
        # We search outside footer to avoid clicking the compose-box send button.
        sent = False
        if not caption_sent:
            # JS: find buttons outside footer — the last one should be the Send button
            try:
                clicked = page.evaluate("""() => {
                    const footer = document.querySelector('footer');
                    const allBtns = Array.from(
                        document.querySelectorAll('button, div[role="button"]')
                    );
                    const modalBtns = allBtns.filter(b => !footer || !footer.contains(b));
                    if (!modalBtns.length) return null;
                    // Send button is the last interactive element in the modal
                    const btn = modalBtns[modalBtns.length - 1];
                    btn.click();
                    return btn.getAttribute('aria-label') || btn.tagName;
                }""")
                if clicked:
                    logger.info('Clicked modal button: %s', clicked)
                    sent = True
            except Exception as e:
                logger.warning('JS modal button click failed: %s', e)

        # Fallback: find send button via JS (handles any icon/aria-label variant)
        if not caption_sent and not sent:
            try:
                clicked = page.evaluate("""() => {
                    const candidates = [
                        document.querySelector('[data-icon="send"]'),
                        document.querySelector('[data-icon="send-white"]'),
                        document.querySelector('button[aria-label="Надіслати"]'),
                        document.querySelector('button[aria-label="Send"]'),
                        document.querySelector('[data-testid="send"]'),
                    ];
                    for (const el of candidates) {
                        if (el) {
                            el.closest('button, div[role="button"]')?.click() || el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                if clicked:
                    sent = True
            except Exception:
                pass

        # Last resort: Enter key sends in media preview modal
        if not sent:
            try:
                page.keyboard.press('Enter')
                sent = True
            except Exception:
                pass

        if not caption_sent and not sent:
            page.screenshot(path='/mnt/f/wa_send_fail.png')
            raise RuntimeError('Send button not found after attaching file. Screenshot: /mnt/f/wa_send_fail.png')

        # 7. Wait for upload to complete — spinner disappears when message is queued.
        #    Falls back to a fixed sleep if the spinner selector changed.
        try:
            page.wait_for_function(
                """() => {
                    const spinners = [
                        '[data-icon="msg-time"]',
                        '[data-testid="msg-loading-spinner"]',
                    ];
                    return spinners.every(s => !document.querySelector(s));
                }""",
                timeout=60_000,
            )
        except Exception:
            time.sleep(5)  # fallback

        self.stdout.write(self.style.SUCCESS(
            f'Sent file: {file_path!r}'
            + (' (with caption)' if caption_sent else ' (no caption)')
        ))
        return caption_sent
