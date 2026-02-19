from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from allauth.socialaccount.signals import social_account_added
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(user_signed_up)
def set_new_user_inactive_and_redirect(sender, request, user, **kwargs):
    # This signal is sent right after a new user signs up (local or social)
    
    # We only care about new users here. `sociallogin` in kwargs indicates social signup.
    sociallogin = kwargs.get('sociallogin')
    
    # If it's a new user (social or local) and we want to enforce approval
    # we set is_active to False.
    # Note: `user_signed_up` is only for *new* users, so `sociallogin.is_existing` is not relevant here for setting is_active.
    # It would be relevant if we were using `social_account_added` for existing users.
    
    # For now, we set all newly signed up users (local or social) to inactive
    # if they don't have a sociallogin. If they have sociallogin, we treat it
    # as a new social user.
    if not user.is_superuser: # Never deactivate superusers
        user.is_active = False
        user.save()


@receiver(social_account_added)
def set_newly_social_connected_user_inactive(sender, request, sociallogin, **kwargs):
    # This signal is sent when a social account is added to an *existing* user.
    # In this specific flow, we don't want to deactivate an existing user,
    # as per the user's clarified logic.
    # However, if an existing user's social account is *just added*, we can still
    # use this to set a flag or perform other actions if needed.
    pass

