"""Gemini-based Q&A service that reads from the docs/ folder."""

from pathlib import Path

from django.conf import settings

_SCOPES = ['https://www.googleapis.com/auth/generative-language']


def _token_path() -> Path:
    return Path(settings.BASE_DIR) / '.gemini_token.json'


def _secrets_path() -> Path:
    return Path(settings.BASE_DIR) / 'client_secrets.json'


def _get_oauth_credentials():
    """Load cached OAuth credentials, refreshing if expired. Returns None if unavailable."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_file = _token_path()
    if not token_file.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), _SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())
        return creds if creds.valid else None
    except Exception:
        return None


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
    """Send question to Gemini using OAuth credentials or API key fallback."""
    try:
        from google import genai
    except ImportError:
        return "Помилка: пакет google-genai не встановлено."

    # Try OAuth credentials first
    creds = _get_oauth_credentials()
    if creds:
        client = genai.Client(credentials=creds)
    else:
        # Fall back to API key
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            return (
                "Gemini не налаштовано. Запустіть авторизацію: "
                "python manage.py gemini_auth"
            )
        client = genai.Client(api_key=api_key)

    try:
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
