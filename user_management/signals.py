import logging
import re
from django.core.cache import cache
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added
from django.contrib.auth import get_user_model
from app_drones.telegram_utils import send_telegram_message, send_admin_message

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(user_signed_up)
def set_new_user_inactive_and_notify_telegram(sender, request, user, **kwargs):
    try:
        if not user.is_superuser:
            user.is_active = False
            user.save()

        full_name = f"{user.first_name} {user.last_name}".strip() or "Без імені"
        social_info = ""
        if kwargs.get('sociallogin'):
            provider = kwargs.get('sociallogin').account.provider
            social_info = f" (через {provider.capitalize()})"

        message = (
            f"<b>🔔 Новий запит на доступ до системи!</b>\n\n"
            f"👤 Користувач: {full_name}\n"
            f"📧 Email: {user.email}\n"
            f"🆔 Username: @{user.username}{social_info}\n\n"
            f"⚠️ Користувач деактивований до підтвердження адміністратором."
        )
        # send_telegram_message(message)
    except Exception:
        logger.exception("user_signed_up signal failed for user %s", user.pk)


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
    try:
        # Cache the new session key for duplicate-Cloudflare-request recovery.
        # pre_social_login sets request._oauth_state_id before login() cycles
        # the session. By the time this signal fires the new key is active.
        state_id = getattr(request, '_oauth_state_id', None)
        if state_id and request.session.session_key:
            from django.conf import settings
            ttl = 30
            cache.set(f'oauth_session_{state_id}', request.session.session_key, timeout=ttl)
            next_url = request.session.get('_oauth_next') or settings.LOGIN_REDIRECT_URL
            cache.set(f'oauth_next_{state_id}', next_url, timeout=ttl)

        from django.utils import timezone
        try:
            name = user.profile.display_name
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
        # send_admin_message(message)
    except Exception:
        logger.exception("user_logged_in signal failed for user %s", user.pk)


@receiver(social_account_added)
def set_newly_social_connected_user_inactive(sender, request, sociallogin, **kwargs):
    # This signal is sent when a social account is added to an *existing* user.
    # In this specific flow, we don't want to deactivate an existing user,
    # as per the user's clarified logic.
    # However, if an existing user's social account is *just added*, we can still
    # use this to set a flag or perform other actions if needed.
    pass

