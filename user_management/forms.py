from django import forms
from django.contrib.auth import get_user_model

from .models import Profile

User = get_user_model()


class ProfileForm(forms.ModelForm):
    callsign = forms.CharField(
        label="Позивний",
        max_length=50,
        required=False,
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, "profile", None)
            if profile:
                self.fields["callsign"].initial = profile.callsign

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and user.pk:
            profile = getattr(user, "profile", None)
            if profile:
                profile.callsign = self.cleaned_data["callsign"]
                profile.save(update_fields=["callsign"])
        return user


class AvatarForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("avatar",)
