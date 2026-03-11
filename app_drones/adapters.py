import logging
import traceback

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        if commit:
            user.save()
        return user

    def get_login_redirect_url(self, request):
        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        return user

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        session_states = request.session.get('socialaccount_states', {})
        logger.error(
            "Social auth error | provider=%s | error=%s"
            "\n  session_key=%s | states_in_session=%s | state_in_GET=%s"
            "\n  sessionid_cookie=%s | HTTP_HOST=%s | HTTP_REFERER=%s\n%s",
            getattr(provider, 'id', provider),
            error,
            request.session.session_key,
            list(session_states.keys()),
            request.GET.get('state', '(missing)'),
            request.COOKIES.get('sessionid', '(missing)'),
            request.META.get('HTTP_HOST', '?'),
            request.META.get('HTTP_REFERER', '?'),
            traceback.format_exc() if exception else '(no traceback)',
        )
        super().on_authentication_error(request, provider, error=error, exception=exception, extra_context=extra_context)
