"""
Authorize Gemini via browser OAuth flow.

Usage:
    python manage.py gemini_auth

Requires client_secrets.json (OAuth 2.0 Desktop App credentials)
downloaded from Google Cloud Console → APIs & Services → Credentials.

Token is saved to .gemini_token.json in the project root and reused
automatically by gemini_service. Refresh is handled transparently.
"""

from django.core.management.base import BaseCommand

from documentation.gemini_service import _secrets_path, _token_path, _SCOPES


class Command(BaseCommand):
    help = 'Authorize Gemini API access via browser (OAuth2)'

    def handle(self, *args, **options):
        secrets = _secrets_path()
        if not secrets.exists():
            self.stderr.write(self.style.ERROR(
                f'client_secrets.json not found at {secrets}\n'
                'Download it from Google Cloud Console:\n'
                '  APIs & Services → Credentials → Create OAuth 2.0 Client ID (Desktop app)'
            ))
            return

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'google-auth-oauthlib is not installed. Run: pip install google-auth-oauthlib'
            ))
            return

        self.stdout.write('Opening browser for Google authentication...')
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets), _SCOPES)
        creds = flow.run_local_server(port=0)

        token_file = _token_path()
        token_file.write_text(creds.to_json())

        self.stdout.write(self.style.SUCCESS(
            f'Authorized successfully. Token saved to {token_file}'
        ))
