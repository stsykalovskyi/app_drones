"""
Authorize Gemini API access.

Option 1 — import from Gemini CLI token (no browser needed):
    python manage.py gemini_auth --from-cli
    Reads ~/.gemini/oauth_creds.json (created by @google/gemini-cli) and
    converts it to .gemini_token.json used by this app.

Option 2 — browser OAuth (requires a GUI browser):
    python manage.py gemini_auth
    Then copy token to server:
      scp .gemini_token.json root@85.121.4.216:/root/MyProjects/python/app_drones/
      ssh -p 2244 root@85.121.4.216 "docker cp /root/MyProjects/python/app_drones/.gemini_token.json app_drones:/app/"
"""

from django.core.management.base import BaseCommand

from documentation.gemini_service import (
    _CLI_CLIENT_ID, _CLI_CLIENT_SECRET, _CLI_TOKEN_PATH, _SCOPES, _token_path,
)


class Command(BaseCommand):
    help = 'Authorize Gemini API access (--from-cli to import existing CLI token)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--from-cli',
            action='store_true',
            help='Import token from ~/.gemini/oauth_creds.json (no browser needed)',
        )

    def handle(self, *args, **options):
        if options['from_cli']:
            self._import_from_cli()
        else:
            self._browser_auth()

    def _import_from_cli(self):
        if not _CLI_TOKEN_PATH.exists():
            self.stderr.write(self.style.ERROR(
                f'CLI token not found: {_CLI_TOKEN_PATH}\n'
                'Run `gemini` CLI first to authorize, then retry.'
            ))
            return
        import json, datetime
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
            creds.expiry = datetime.datetime.utcfromtimestamp(raw['expiry_date'] / 1000)
        token_file = _token_path()
        token_file.write_text(creds.to_json())
        self.stdout.write(self.style.SUCCESS(
            f'CLI token imported to {token_file}'
        ))

    def _browser_auth(self):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            self.stderr.write(self.style.ERROR('Run: pip install google-auth-oauthlib'))
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
        self.stdout.write(self.style.SUCCESS(f'Token saved to {token_file}'))
        self.stdout.write(
            f'\nTo deploy to server:\n'
            f'  scp {token_file} root@85.121.4.216:/root/MyProjects/python/app_drones/\n'
            f'  ssh -p 2244 root@85.121.4.216 '
            f'"docker cp /root/MyProjects/python/app_drones/.gemini_token.json app_drones:/app/"'
        )
