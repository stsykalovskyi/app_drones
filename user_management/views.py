from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AvatarForm, ProfileForm
from .models import Profile

User = get_user_model()


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
    profile, _ = Profile.objects.get_or_create(user=user)

    if request.method == "POST":
        # Initialize forms for POST request (will be updated if a specific form is submitted)
        profile_form = ProfileForm(instance=user)
        password_form = PasswordChangeForm(user)
        avatar_form = AvatarForm(instance=profile)

        if "change_password" in request.POST:
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Пароль змінено")
                return redirect("user_management:profile")
            # If form is invalid, profile_form and avatar_form retain their initial values
            # and password_form is updated with errors.
        elif "delete_avatar" in request.POST:
            if profile.avatar:
                profile.avatar.delete()
                profile.save()
                messages.success(request, "Фото видалено")
            return redirect("user_management:profile")
            # If redirect doesn't happen, forms need to be passed to render
        elif "change_avatar" in request.POST:
            avatar_form = AvatarForm(
                request.POST, request.FILES, instance=profile
            )
            if avatar_form.is_valid():
                avatar_form.save()
                messages.success(request, "Фото оновлено")
                return redirect("user_management:profile")
            # If form is invalid, profile_form and password_form retain their initial values
            # and avatar_form is updated with errors.
        else: # Default profile update form submission
            profile_form = ProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Профіль оновлено")
                return redirect("user_management:profile")
            # If form is invalid, password_form and avatar_form retain their initial values
            # and profile_form is updated with errors.
    else:
        profile_form = ProfileForm(instance=user)
        password_form = PasswordChangeForm(user)
        avatar_form = AvatarForm(instance=profile)

    return render(request, "user_management/profile.html", {
        "profile_form": profile_form,
        "password_form": password_form,
        "avatar_form": avatar_form,
        "profile": profile,
    })


@login_required
def approval_pending_view(request):
    """
    Renders a page informing the user that their account is pending approval.
    """
    return render(request, "user_management/approval_pending.html")


@login_required
def user_list_view(request):
    if not request.real_user.is_superuser:
        raise PermissionDenied
    users = (
        User.objects.select_related('profile')
        .filter(is_active=True)
        .exclude(is_superuser=True)
        .order_by('profile__callsign', 'username')
    )
    return render(request, "user_management/user_list.html", {'users': users})


@login_required
def impersonate_start(request, user_id):
    if not request.real_user.is_superuser:
        raise PermissionDenied
    target = get_object_or_404(User, pk=user_id)
    if target.is_superuser:
        raise PermissionDenied
    original_pk = request.real_user.pk
    login(request, target, backend='django.contrib.auth.backends.ModelBackend')
    request.session['_impersonate'] = original_pk
    return redirect('home')


@login_required
def impersonate_stop(request):
    original_id = request.session.pop('_impersonate', None)
    if not original_id:
        return redirect('home')
    original = get_object_or_404(User, pk=original_id)
    login(request, original, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('home')
