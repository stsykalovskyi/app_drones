"""
Authorize Gemini via browser OAuth flow (same credentials as @google/gemini-cli).

Usage:
    python manage.py gemini_auth

Opens a browser window for Google login. Token is saved to .gemini_token.json
and reused automatically. No client_secrets.json needed.
"""

from django.core.management.base import BaseCommand

from documentation.gemini_service import (
    _CLI_CLIENT_ID, _CLI_CLIENT_SECRET, _SCOPES, _token_path,
)


class Command(BaseCommand):
    help = 'Authorize Gemini API access via browser (OAuth2)'

    def handle(self, *args, **options):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'Run: pip install google-auth-oauthlib'
            ))
            return

        client_config = {
            'installed': {
                'client_id': _CLI_CLIENT_ID,
                'client_secret': _CLI_CLIENT_SECRET,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': ['urn:ietf:wg:oauth:2.0:oob', 'http://localhost'],
            }
        }

        self.stdout.write('Opening browser for Google authentication...')
        flow = InstalledAppFlow.from_client_config(client_config, _SCOPES)
        creds = flow.run_local_server(port=0)

        token_file = _token_path()
        token_file.write_text(creds.to_json())
        self.stdout.write(self.style.SUCCESS(
            f'Authorized successfully. Token saved to {token_file}'
        ))
