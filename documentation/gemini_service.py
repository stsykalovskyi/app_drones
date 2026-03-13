"""Gemini-based Q&A for the documentation knowledge base.

Auth: API key via GEMINI_API_KEY setting.
Model: gemini-2.5-flash (free tier available).
"""

import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_client():
    from google import genai
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in settings.")
    return genai.Client(api_key=api_key)


def _load_docs_context() -> str:
    """Load active documents from KnowledgeDocument DB records (pre-extracted text)."""
    try:
        from documentation.models import KnowledgeDocument
        docs = KnowledgeDocument.objects.filter(
            is_active=True, status=KnowledgeDocument.STATUS_READY
        ).exclude(extracted_text='')
        parts = [f"=== {doc.title} ===\n{doc.extracted_text}" for doc in docs]
        return '\n\n'.join(parts)
    except Exception:
        return ''


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text from PDF. Tries text layer first, falls back to OCR."""
    logger.info('Extracting text from: %s', file_path)

    # 1. Try text layer (fast, free)
    try:
        import pypdf
        reader = pypdf.PdfReader(str(file_path))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages).strip()
        if len(text) > 100:
            logger.info('Text layer extracted: %d chars', len(text))
            return text
        logger.info('Text layer too short (%d chars), trying OCR', len(text))
    except Exception as e:
        logger.warning('pypdf failed: %s', e)

    # 2. OCR fallback via pytesseract + PyMuPDF (no poppler needed)
    try:
        import io
        import fitz  # PyMuPDF
        import PIL.Image
        import pytesseract
        logger.info('Starting OCR (PyMuPDF + tesseract) for %s', file_path.name)
        doc = fitz.open(str(file_path))
        logger.info('Opened PDF: %d pages', len(doc))
        pages = []
        mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat)
            img = PIL.Image.open(io.BytesIO(pix.tobytes('png')))
            page_text = pytesseract.image_to_string(img, lang='ukr+rus')
            logger.info('Page %d/%d: %d chars', i + 1, len(doc), len(page_text))
            pages.append(page_text)
        result = '\n'.join(pages).strip()
        logger.info('OCR complete: %d total chars', len(result))
        return result
    except ImportError as e:
        logger.error('OCR dependency missing: %s', e)
    except Exception as e:
        logger.exception('OCR failed for %s: %s', file_path.name, e)

    logger.error('All extraction methods failed for %s', file_path.name)
    return ''


def ask_gemini(question: str, is_superuser: bool = False) -> str:
    """Send question to Gemini with docs context.

    Regular users: answers restricted to docs/ knowledge base only.
    Superusers: may use general knowledge in addition to docs.
    """
    try:
        client = _get_client()
    except RuntimeError as e:
        return str(e)

    docs_context = _load_docs_context()

    if is_superuser:
        if docs_context:
            system_text = (
                "Ти — асистент майстерні БПЛА з повним доступом.\n"
                "Відповідай на будь-які питання, використовуючи наведену документацію та загальні знання.\n\n"
                f"ДОКУМЕНТАЦІЯ:\n{docs_context}"
            )
        else:
            system_text = (
                "Ти — асистент майстерні БПЛА з повним доступом. "
                "Відповідай на основі загальних знань."
            )
    else:
        if not docs_context:
            return "База знань порожня. Зверніться до адміністратора."
        system_text = (
            "Ти — асистент майстерні БПЛА. Відповідай ВИКЛЮЧНО на основі наданої документації. "
            "Якщо відповідь не міститься в документації — повідом, що ця інформація відсутня в базі знань. "
            "Не використовуй жодних загальних знань поза межами документації.\n\n"
            f"ДОКУМЕНТАЦІЯ:\n{docs_context}"
        )

    try:
        from google.genai import types
        response = client.models.generate_content(
            model='models/gemini-2.5-flash',
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=system_text,
                temperature=0.7,
            ),
        )
        return response.text.strip()
    except Exception as exc:
        return f"Помилка Gemini API: {exc}"
