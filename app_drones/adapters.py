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
        session_key = request.session.session_key
        session_states = request.session.get('socialaccount_states', {})
        state_id_in_get = request.GET.get('state', '(missing)')
        logger.error(
            "Social auth error | provider=%s | error=%s | exception=%s"
            "\n  session_key=%s | states_in_session=%s | state_in_GET=%s"
            "\n  GET params=%s\n%s",
            getattr(provider, 'id', provider),
            error,
            exception,
            session_key,
            list(session_states.keys()),
            state_id_in_get,
            dict(request.GET),
            traceback.format_exc() if exception else '(no traceback)',
        )
        super().on_authentication_error(request, provider, error=error, exception=exception, extra_context=extra_context)
