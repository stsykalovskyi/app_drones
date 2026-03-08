import re
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added
from django.contrib.auth import get_user_model
from app_drones.telegram_utils import send_telegram_message, send_admin_message

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


def _parse_ua(ua: str) -> str:
    """Extract a short browser/OS label from the User-Agent string."""
    ua = ua or ''
    browser = 'Невідомо'
    os_name = ''
    if 'Edg/' in ua or 'EdgA/' in ua:
        browser = 'Edge'
    elif 'Chrome/' in ua and 'Safari/' in ua:
        browser = 'Chrome'
    elif 'Firefox/' in ua:
        browser = 'Firefox'
    elif 'Safari/' in ua and 'Chrome/' not in ua:
        browser = 'Safari'
    elif 'MSIE' in ua or 'Trident/' in ua:
        browser = 'IE'
    if 'Android' in ua:
        os_name = 'Android'
    elif 'iPhone' in ua or 'iPad' in ua:
        os_name = 'iOS'
    elif 'Windows' in ua:
        os_name = 'Windows'
    elif 'Macintosh' in ua:
        os_name = 'macOS'
    elif 'Linux' in ua:
        os_name = 'Linux'
    return f"{browser} / {os_name}" if os_name else browser


def _get_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '—')


@receiver(user_logged_in)
def notify_admin_on_login(sender, request, user, **kwargs):
    from django.utils import timezone
    try:
        profile = user.profile
        name = profile.display_name
    except Exception:
        name = user.get_full_name() or user.username

    now = timezone.localtime(timezone.now())
    date_str = now.strftime('%d.%m.%Y %H:%M')
    ip = _get_ip(request)
    ua = _parse_ua(request.META.get('HTTP_USER_AGENT', ''))

    message = (
        f"🔐 <b>Вхід до системи</b>\n\n"
        f"👤 {name} (@{user.username})\n"
        f"🕐 {date_str}\n"
        f"🌐 IP: <code>{ip}</code>\n"
        f"📱 {ua}"
    )
    send_admin_message(message)


@receiver(social_account_added)
def set_newly_social_connected_user_inactive(sender, request, sociallogin, **kwargs):
    # This signal is sent when a social account is added to an *existing* user.
    # In this specific flow, we don't want to deactivate an existing user,
    # as per the user's clarified logic.
    # However, if an existing user's social account is *just added*, we can still
    # use this to set a flag or perform other actions if needed.
    pass

