from django.core.management.base import BaseCommand
from django.conf import settings
from app_drones.telegram_utils import send_telegram_message

class Command(BaseCommand):
    help = 'Sends a test message to Telegram to verify bot configuration.'

    def add_arguments(self, parser):
        parser.add_argument(
            'message', 
            type=str, 
            nargs='?', 
            default='🔔 Тестове повідомлення від системи "Майстерня". Бот налаштований вірно!',
            help='The message to send (optional)'
        )

    def handle(self, *args, **options):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
        message = options['message']

        self.stdout.write(self.style.NOTICE(f"Testing Telegram bot..."))
        self.stdout.write(f"TELEGRAM_BOT_TOKEN: {token[:10]}..." if token else "TELEGRAM_BOT_TOKEN: NOT SET")
        self.stdout.write(f"TELEGRAM_CHAT_ID: {chat_id}" if chat_id else "TELEGRAM_CHAT_ID: NOT SET")

        if not token or not chat_id:
            self.stdout.write(self.style.ERROR("Error: Telegram settings are missing in your .env file!"))
            return

        try:
            # We call the utility function
            send_telegram_message(message)
            self.stdout.write(self.style.SUCCESS(f"Successfully sent message: '{message}'"))
            self.stdout.write(self.style.NOTICE("Check your Telegram chat/channel."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to send message: {e}"))
