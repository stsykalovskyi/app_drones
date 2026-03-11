"""Gemini-based Q&A service that reads from the docs/ folder."""

from pathlib import Path

from django.conf import settings


def _load_docs_context() -> str:
    """Read all supported files from DOCS_FOLDER and return combined text."""
    docs_path = Path(getattr(settings, 'DOCS_FOLDER', settings.BASE_DIR / 'docs'))
    if not docs_path.exists():
        return ""

    parts = []
    for file_path in sorted(docs_path.rglob('*')):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()

        if suffix in ('.txt', '.md'):
            try:
                text = file_path.read_text(encoding='utf-8', errors='ignore').strip()
                if text:
                    parts.append(f"=== {file_path.name} ===\n{text}")
            except Exception:
                pass

        elif suffix == '.pdf':
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                text = '\n'.join(
                    page.extract_text() or '' for page in reader.pages
                ).strip()
                if text:
                    parts.append(f"=== {file_path.name} ===\n{text}")
            except ImportError:
                parts.append(f"=== {file_path.name} === [PDF — pypdf не встановлено]")
            except Exception:
                pass

    return '\n\n'.join(parts)


def ask_gemini(question: str) -> str:
    """Send question to Gemini, using docs as context. Returns answer string."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return "Gemini API не налаштовано. Зверніться до адміністратора."

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        docs_context = _load_docs_context()

        if docs_context:
            prompt = (
                "Ти — асистент майстерні БПЛА. Відповідай на питання виключно "
                "на основі наданої документації. Якщо відповідь відсутня в "
                "документації — так і скажи.\n\n"
                f"ДОКУМЕНТАЦІЯ:\n{docs_context}\n\n"
                f"ПИТАННЯ: {question}\n\nВІДПОВІДЬ:"
            )
        else:
            prompt = (
                "Ти — асистент майстерні БПЛА. Документація відсутня. "
                "Відповідай на основі загальних знань про БПЛА та технічне "
                f"обслуговування.\n\nПИТАННЯ: {question}\n\nВІДПОВІДЬ:"
            )

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        return response.text.strip()

    except Exception as exc:
        return f"Помилка при зверненні до Gemini: {exc}"
