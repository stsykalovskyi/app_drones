import requests
import logging
from django.conf import settings
from user_management.models import Profile

logger = logging.getLogger(__name__)


def _post_message(token: str, chat_id: str, text: str) -> None:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code != 200:
            logger.error("Telegram API error for %s: %s", chat_id, r.text)
    except requests.exceptions.RequestException as e:
        logger.error("Failed to send Telegram message to %s: %s", chat_id, e)


def send_admin_message(message: str) -> None:
    """Send a message only to the primary admin chat (TELEGRAM_CHAT_ID)."""
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
    if not token or not chat_id:
        logger.warning("Admin Telegram notification skipped: token or chat_id not set.")
        return
    _post_message(token, str(chat_id), message)


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

    for chat_id in recipients:
        _post_message(token, chat_id, message)
