from django.contrib import messages
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import ProfileForm


class CustomLoginView(LoginView):
    """Login view that redirects inactive users to the account-inactive page."""

    template_name = "registration/login.html"

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")

        # Try to authenticate allowing inactive users.
        user = authenticate(request, username=username, password=password)

        if user is None:
            # Django's default ModelBackend rejects inactive users and returns
            # None, so manually check whether the credentials belong to an
            # inactive account.
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                candidate = User.objects.get(username=username)
                if not candidate.is_active and candidate.check_password(password):
                    return redirect("account_inactive")
            except User.DoesNotExist:
                pass

        return super().post(request, *args, **kwargs)


@login_required
def profile_view(request):
    user = request.user
    if request.method == "POST":
        if "change_password" in request.POST:
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Пароль змінено")
                return redirect("user_management:profile")
            profile_form = ProfileForm(instance=user)
        else:
            profile_form = ProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Профіль оновлено")
                return redirect("user_management:profile")
            password_form = PasswordChangeForm(user)
    else:
        profile_form = ProfileForm(instance=user)
        password_form = PasswordChangeForm(user)

    return render(request, "user_management/profile.html", {
        "profile_form": profile_form,
        "password_form": password_form,
    })


@login_required
def approval_pending_view(request):
    """
    Renders a page informing the user that their account is pending approval.
    """
    return render(request, "user_management/approval_pending.html")