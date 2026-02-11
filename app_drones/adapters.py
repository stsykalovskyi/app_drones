from django.urls import reverse
from django.conf import settings
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.auth_backends import AuthenticationBackend as AllauthAuthenticationBackend


class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.is_active = False
        if commit:
            user.save()
        return user

    def get_login_redirect_url(self, request):
        if not request.user.is_active:
            # If user is not active, redirect to approval pending page
            return reverse('user_management:approval_pending')
        # Otherwise, use the default login redirect URL
        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.is_active = False
        user.save()
        return user

class CustomAuthenticationBackend(AllauthAuthenticationBackend):
    def authenticate(self, request, **credentials):
        # Authenticate user normally, ignoring is_active initially
        user = super().authenticate(request, **credentials)
        return user

