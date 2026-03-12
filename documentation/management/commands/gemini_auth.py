"""
Authorize Gemini via browser OAuth flow (same credentials as @google/gemini-cli).

Run LOCALLY (requires a browser):
    python manage.py gemini_auth

Then copy the token to the server:
    scp .gemini_token.json root@85.121.4.216:/root/MyProjects/python/app_drones/

Token is reused automatically on next request. No client_secrets.json needed.
"""

from django.core.management.base import BaseCommand

from documentation.gemini_service import (
    _CLI_CLIENT_ID, _CLI_CLIENT_SECRET, _SCOPES, _token_path,
)


class Command(BaseCommand):
    help = 'Authorize Gemini API access via browser OAuth2 (run locally, then copy token to server)'

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
                'redirect_uris': ['http://localhost'],
            }
        }

        self.stdout.write('Opening browser for Google authentication...')
        flow = InstalledAppFlow.from_client_config(client_config, _SCOPES)
        creds = flow.run_local_server(port=0)

        token_file = _token_path()
        token_file.write_text(creds.to_json())
        self.stdout.write(self.style.SUCCESS(
            f'Token saved to {token_file}'
        ))
        self.stdout.write(
            f'\nTo deploy to server run:\n'
            f'  scp {token_file} root@85.121.4.216:/root/MyProjects/python/app_drones/\n'
            f'Then restart the Docker container:\n'
            f'  ssh -p 2244 root@85.121.4.216 "docker cp /root/MyProjects/python/app_drones/.gemini_token.json app_drones:/app/"'
        )
