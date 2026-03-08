from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added
from django.contrib.auth import get_user_model
from app_drones.telegram_utils import send_telegram_message

User = get_user_model()


@receiver(user_signed_up)
def set_new_user_inactive_and_notify_telegram(sender, request, user, **kwargs):
    # This signal is sent right after a new user signs up (local or social)
    
    # For now, we set all newly signed up users (local or social) to inactive
    if not user.is_superuser: # Never deactivate superusers
        user.is_active = False
        user.save()

    # Повідомляємо в Telegram про новий запит
    full_name = f"{user.first_name} {user.last_name}".strip() or "Без імені"
    email = user.email
    username = user.username
    social_info = ""
    if kwargs.get('sociallogin'):
        provider = kwargs.get('sociallogin').account.provider
        social_info = f" (через {provider.capitalize()})"

    message = (
        f"<b>🔔 Новий запит на доступ до системи!</b>\n\n"
        f"👤 Користувач: {full_name}\n"
        f"📧 Email: {email}\n"
        f"🆔 Username: @{username}{social_info}\n\n"
        f"⚠️ Користувач деактивований до підтвердження адміністратором."
    )
    send_telegram_message(message)


@receiver(social_account_added)
def set_newly_social_connected_user_inactive(sender, request, sociallogin, **kwargs):
    # This signal is sent when a social account is added to an *existing* user.
    # In this specific flow, we don't want to deactivate an existing user,
    # as per the user's clarified logic.
    # However, if an existing user's social account is *just added*, we can still
    # use this to set a flag or perform other actions if needed.
    pass

