"""Gemini-based Q&A via the same Cloud Code endpoint used by @google/gemini-cli.

Auth: OAuth2 user credentials (cloud-platform scope).
Endpoint: https://cloudcode-pa.googleapis.com/v1internal:generateContent
This endpoint has no free-tier quota exhaustion — it's the same one the CLI uses.
"""

import datetime
import json
from pathlib import Path

from django.conf import settings

# OAuth client shared with the official Gemini CLI
_CLI_CLIENT_ID = 'GEMINI_CLI_CLIENT_ID_PLACEHOLDER'
_CLI_CLIENT_SECRET = 'GEMINI_CLI_CLIENT_SECRET_PLACEHOLDER'
_SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

# Gemini CLI stores its token and project here
_CLI_TOKEN_PATH = Path.home() / '.gemini' / 'oauth_creds.json'
_CLI_PROJECTS_PATH = Path.home() / '.gemini' / 'projects.json'

# Code Assist API (same as Gemini CLI uses)
_CODE_ASSIST_URL = 'https://cloudcode-pa.googleapis.com/v1internal:generateContent'
_MODEL = 'gemini-2.5-flash'

_cached_project_id: str | None = None


def _token_path() -> Path:
    return Path(settings.BASE_DIR) / '.gemini_token.json'


def _get_project_id(token: str) -> str:
    """Get the managed Cloud project ID via loadCodeAssist. Cached for process lifetime."""
    global _cached_project_id
    if _cached_project_id:
        return _cached_project_id
    import httpx
    try:
        resp = httpx.post(
            'https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            json={
                'cloudaicompanionProject': None,
                'metadata': {
                    'ideType': 'IDE_UNSPECIFIED',
                    'platform': 'PLATFORM_UNSPECIFIED',
                    'pluginType': 'GEMINI',
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        _cached_project_id = data.get('cloudaicompanionProject') or ''
        return _cached_project_id
    except Exception:
        return ''


def _load_cli_credentials():
    """Convert ~/.gemini/oauth_creds.json (CLI format) to google-auth Credentials."""
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
        if raw.get('expiry_date'):
            # google-auth uses timezone-naive UTC datetimes internally
            creds.expiry = datetime.datetime.utcfromtimestamp(raw['expiry_date'] / 1000)
        return creds
    except Exception:
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


def _get_valid_token() -> str | None:
    """Return a valid OAuth access token string, refreshing if needed."""
    from google.auth.transport.requests import Request

    for loader in (_load_our_credentials, _load_cli_credentials):
        creds = loader()
        if creds is None:
            continue
        try:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                _token_path().write_text(creds.to_json())
            if creds.valid:
                return creds.token
        except Exception:
            continue
    return None


def _load_docs_context() -> str:
    """Read all supported files from DOCS_FOLDER recursively and return combined text."""
    docs_path = Path(getattr(settings, 'DOCS_FOLDER', settings.BASE_DIR / 'docs'))
    if not docs_path.exists():
        return ""

    parts = []
    for file_path in sorted(docs_path.rglob('*')):
        if not file_path.is_file() or file_path.name.startswith('.'):
            continue
        suffix = file_path.suffix.lower()
        rel_name = file_path.relative_to(docs_path)

        if suffix in ('.txt', '.md'):
            try:
                text = file_path.read_text(encoding='utf-8', errors='ignore').strip()
                if text:
                    parts.append(f"=== {rel_name} ===\n{text}")
            except Exception:
                pass

        elif suffix == '.pdf':
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                text = '\n'.join(page.extract_text() or '' for page in reader.pages).strip()
                if text:
                    parts.append(f"=== {rel_name} ===\n{text}")
            except ImportError:
                pass
            except Exception:
                pass

        elif suffix == '.docx':
            try:
                import docx
                doc = docx.Document(str(file_path))
                text = '\n'.join(p.text for p in doc.paragraphs if p.text.strip()).strip()
                if text:
                    parts.append(f"=== {rel_name} ===\n{text}")
            except ImportError:
                pass
            except Exception:
                pass

    return '\n\n'.join(parts)


def ask_gemini(question: str) -> str:
    """Send question to Gemini via Cloud Code endpoint (same as Gemini CLI)."""
    import httpx

    token = _get_valid_token()
    if not token:
        return "Gemini не авторизовано. Запустіть: python manage.py gemini_auth"

    project_id = _get_project_id(token)

    docs_context = _load_docs_context()
    if docs_context:
        system_text = (
            "Ти — асистент майстерні БПЛА. Відповідай на питання виключно "
            "на основі наданої документації. Якщо відповідь відсутня — так і скажи.\n\n"
            f"ДОКУМЕНТАЦІЯ:\n{docs_context}"
        )
    else:
        system_text = (
            "Ти — асистент майстерні БПЛА. Відповідай на основі загальних знань про БПЛА."
        )

    body = {
        "model": _MODEL,
        "project": project_id,
        "request": {
            "contents": [{"role": "user", "parts": [{"text": question}]}],
            "systemInstruction": {"parts": [{"text": system_text}]},
            "generationConfig": {"temperature": 0.7, "topP": 0.95},
        },
    }

    try:
        resp = httpx.post(
            _CODE_ASSIST_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # Response wraps standard Gemini response in "response" key
        inner = data.get('response', data)
        candidates = inner.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            return ''.join(p.get('text', '') for p in parts).strip()
        return "Відповідь порожня."
    except httpx.HTTPStatusError as e:
        return f"Помилка API ({e.response.status_code}): {e.response.text[:300]}"
    except Exception as exc:
        return f"Помилка: {exc}"
