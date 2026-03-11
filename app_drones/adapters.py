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
        logger.error(
            "Social auth error | provider=%s | error=%s | exception=%s\n%s",
            getattr(provider, 'id', provider),
            error,
            exception,
            traceback.format_exc() if exception else '(no traceback)',
        )
        super().on_authentication_error(request, provider, error=error, exception=exception, extra_context=extra_context)
