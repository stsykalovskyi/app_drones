"""Gemini-based Q&A via the same Cloud Code endpoint used by @google/gemini-cli.

Auth: OAuth2 user credentials (cloud-platform scope).
Endpoint: https://cloudcode-pa.googleapis.com/v1internal:generateContent
This endpoint has no free-tier quota exhaustion — it's the same one the CLI uses.
"""

import datetime
import json
from pathlib import Path
from typing import Optional

from django.conf import settings

# OAuth client shared with the official Gemini CLI (set via env vars)
_CLI_CLIENT_ID = getattr(settings, 'GEMINI_CLI_CLIENT_ID', '')
_CLI_CLIENT_SECRET = getattr(settings, 'GEMINI_CLI_CLIENT_SECRET', '')
_SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

# Gemini CLI stores its token and project here
_CLI_TOKEN_PATH = Path.home() / '.gemini' / 'oauth_creds.json'
_CLI_PROJECTS_PATH = Path.home() / '.gemini' / 'projects.json'

# Code Assist API (same as Gemini CLI uses)
_CODE_ASSIST_URL = 'https://cloudcode-pa.googleapis.com/v1internal:generateContent'
_MODELS = ['gemini-2.5-flash']

_cached_project_id: Optional[str] = None


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


def _get_valid_token() -> Optional[str]:
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


_SKIP_DIRS = {
    '.git', '.venv', 'venv', '__pycache__', 'node_modules',
    'migrations', 'staticfiles', 'static', 'media', 'docs',
    '.github', 'backups', 'whatsapp_session',
}
_PROJECT_EXTENSIONS = {'.py', '.html', '.txt', '.md'}
_MAX_FILE_BYTES = 50_000  # skip very large files
_MAX_PROJECT_BYTES = 400_000  # total context cap


def _load_project_context() -> str:
    """Read project source files (Python, HTML, txt, md) for superadmin context."""
    base = Path(settings.BASE_DIR)
    parts = []
    total = 0

    for file_path in sorted(base.rglob('*')):
        if not file_path.is_file():
            continue
        # skip excluded dirs
        if any(part in _SKIP_DIRS for part in file_path.parts):
            continue
        if file_path.name.startswith('.'):
            continue
        if file_path.suffix.lower() not in _PROJECT_EXTENSIONS:
            continue
        if file_path.stat().st_size > _MAX_FILE_BYTES:
            continue

        try:
            text = file_path.read_text(encoding='utf-8', errors='ignore').strip()
        except Exception:
            continue
        if not text:
            continue

        rel = file_path.relative_to(base)
        entry = f"=== {rel} ===\n{text}"
        if total + len(entry) > _MAX_PROJECT_BYTES:
            break
        parts.append(entry)
        total += len(entry)

    return '\n\n'.join(parts)


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


def ask_gemini(question: str, is_superuser: bool = False) -> str:
    """Send question to Gemini via Cloud Code endpoint (same as Gemini CLI).

    Regular users: answers restricted strictly to the docs/ knowledge base.
    Superusers: unrestricted — Gemini may use general knowledge as well.
    """
    import httpx

    token = _get_valid_token()
    if not token:
        return "Gemini не авторизовано. Запустіть: python manage.py gemini_auth"

    project_id = _get_project_id(token)

    docs_context = _load_docs_context()

    if is_superuser:
        project_context = _load_project_context()
        context_parts = []
        if docs_context:
            context_parts.append(f"БАЗА ЗНАНЬ (docs/):\n{docs_context}")
        if project_context:
            context_parts.append(f"ФАЙЛИ ПРОЕКТУ:\n{project_context}")
        combined = '\n\n'.join(context_parts)
        if combined:
            system_text = (
                "Ти — асистент майстерні БПЛА з повним доступом до проекту.\n"
                "Відповідай на будь-які питання, використовуючи наведені файли проекту "
                "та загальні знання.\n\n"
                f"{combined}"
            )
        else:
            system_text = (
                "Ти — асистент майстерні БПЛА з повним доступом.\n"
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

    request_body = {
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "systemInstruction": {"parts": [{"text": system_text}]},
        "generationConfig": {"temperature": 0.7, "topP": 0.95},
    }

    last_error = "Невідома помилка"
    for model in _MODELS:
        body = {"model": model, "project": project_id, "request": request_body}
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
            if resp.status_code == 429:
                last_error = f"Помилка API (429): модель {model} недоступна"
                continue
            resp.raise_for_status()
            data = resp.json()
            inner = data.get('response', data)
            candidates = inner.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                return ''.join(p.get('text', '') for p in parts).strip()
            return "Відповідь порожня."
        except httpx.HTTPStatusError as e:
            last_error = f"Помилка API ({e.response.status_code}): {e.response.text[:200]}"
            if e.response.status_code != 429:
                return last_error
        except Exception as exc:
            return f"Помилка: {exc}"

    return last_error
