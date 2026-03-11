import logging
import traceback

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.base import AuthError
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.urls import reverse

logger = logging.getLogger(__name__)

_OAUTH_CACHE_TTL = 30  # seconds


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

    def pre_social_login(self, request, sociallogin):
        # Store state id on the request so the user_logged_in signal can cache
        # the new session key for the duplicate Cloudflare request recovery.
        state_id = request.GET.get('state', '')
        if state_id:
            request._oauth_state_id = state_id
        super().pre_social_login(request, sociallogin)

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

        # Cloudflare sometimes routes the same OAuth callback through two edge
        # nodes simultaneously. Gunicorn (single worker) processes them in
        # sequence: the first consumes the state and logs the user in (cycling
        # the session); the second finds the state gone (error=unknown).
        #
        # Recovery: the user_logged_in signal stores the new session key in
        # cache keyed by state id. Here we read it back and return the same
        # Set-Cookie + redirect that the first request returned, so the user
        # ends up logged in regardless of which response Cloudflare delivers.
        if error == AuthError.UNKNOWN and exception is None:
            state_id = request.GET.get('state', '')
            new_session_key = cache.get(f'oauth_session_{state_id}') if state_id else None
            if new_session_key:
                redirect_url = cache.get(f'oauth_next_{state_id}') or settings.LOGIN_REDIRECT_URL
                response = HttpResponseRedirect(redirect_url)
                response.set_cookie(
                    settings.SESSION_COOKIE_NAME,
                    new_session_key,
                    max_age=settings.SESSION_COOKIE_AGE,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path=settings.SESSION_COOKIE_PATH,
                    secure=settings.SESSION_COOKIE_SECURE,
                    httponly=settings.SESSION_COOKIE_HTTPONLY,
                    samesite=settings.SESSION_COOKIE_SAMESITE,
                )
                raise ImmediateHttpResponse(response)
            # Login didn't complete (e.g. user inactive) — go to login page.
            raise ImmediateHttpResponse(HttpResponseRedirect(reverse('login')))

        super().on_authentication_error(request, provider, error=error, exception=exception, extra_context=extra_context)
