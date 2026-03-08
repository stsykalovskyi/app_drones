import requests
import logging
from django.conf import settings
from user_management.models import Profile

logger = logging.getLogger(__name__)

def send_telegram_message(message: str):
    """
    Sends a message to:
    1. The primary TELEGRAM_CHAT_ID from .env
    2. All verified users from Profile with a stored telegram_chat_id
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    primary_chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)

    if not token:
        logger.warning("Telegram notification skipped: TELEGRAM_BOT_TOKEN not set.")
        return

    # Collect all recipients
    recipients = set()
    if primary_chat_id:
        recipients.add(str(primary_chat_id))
    
    # Add all users who verified their Telegram
    verified_ids = Profile.objects.exclude(telegram_chat_id__isnull=True).exclude(telegram_chat_id='').values_list('telegram_chat_id', flat=True)
    for cid in verified_ids:
        recipients.add(str(cid))

    if not recipients:
        logger.info("No recipients for Telegram message.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    for chat_id in recipients:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Telegram API Error for {chat_id}: {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
