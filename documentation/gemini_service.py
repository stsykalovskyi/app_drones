"""Gemini-based Q&A service that reads from the docs/ folder."""

import datetime
import json
from pathlib import Path

from django.conf import settings

# OAuth credentials shared with the official Gemini CLI (@google/gemini-cli)
_CLI_CLIENT_ID = 'GEMINI_CLI_CLIENT_ID_PLACEHOLDER'
_CLI_CLIENT_SECRET = 'GEMINI_CLI_CLIENT_SECRET_PLACEHOLDER'
_SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

# Gemini CLI stores its token here
_CLI_TOKEN_PATH = Path.home() / '.gemini' / 'oauth_creds.json'


def _token_path() -> Path:
    """Our own cached token (Python google-auth format)."""
    return Path(settings.BASE_DIR) / '.gemini_token.json'


def _load_cli_credentials():
    """Load and convert ~/.gemini/oauth_creds.json (Gemini CLI format) to google-auth Credentials."""
    if not _CLI_TOKEN_PATH.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        raw = json.loads(_CLI_TOKEN_PATH.read_text())
        creds = Credentials(
            token=raw.get('access_token'),
            refresh_token=raw.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=_CLI_CLIENT_ID,
            client_secret=_CLI_CLIENT_SECRET,
            scopes=raw.get('scope', '').split(),
        )
        if raw.get('expiry_date'):  # CLI stores ms timestamp
            creds.expiry = datetime.datetime.fromtimestamp(
                raw['expiry_date'] / 1000, tz=datetime.timezone.utc
            )
        return creds
    except Exception:
        return None


def _get_oauth_credentials():
    """Return valid OAuth credentials, refreshing if needed. Returns None if unavailable."""
    from google.auth.transport.requests import Request

    # Try our own cached token first, then fall back to CLI token
    for loader in (_load_our_credentials, _load_cli_credentials):
        creds = loader()
        if creds is None:
            continue
        try:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                _token_path().write_text(creds.to_json())
            if creds.valid:
                return creds
        except Exception:
            continue
    return None


def _load_our_credentials():
    """Load from our own .gemini_token.json (google-auth JSON format)."""
    token_file = _token_path()
    if not token_file.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        return Credentials.from_authorized_user_file(str(token_file), _SCOPES)
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
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            return (
                "Gemini не налаштовано. Запустіть: python manage.py gemini_auth"
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
