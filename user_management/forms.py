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
    phone_number = forms.CharField(
        label="Номер телефону",
        max_length=20,
        required=False,
        help_text="Формат: +380XXXXXXXXX"
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if not phone:
            return phone
            
        # Remove all non-digit characters except the leading '+'
        # If user entered 097... -> +38097...
        import re
        
        # Strip all whitespace and special characters
        phone = "".join(phone.split())
        
        if not phone.startswith('+'):
            if phone.startswith('380'):
                phone = '+' + phone
            elif phone.startswith('0'):
                phone = '+38' + phone
            else:
                raise forms.ValidationError("Номер телефону має починатися з '+' (наприклад, +380...)")
        
        # Verify it contains only digits after '+'
        if not re.match(r'^\+\d{10,15}$', phone):
            raise forms.ValidationError("Невірний формат номера. Використовуйте тільки цифри (мінімум 10) після '+'.")
            
        return phone

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, "profile", None)
            if profile:
                self.fields["callsign"].initial = profile.callsign
                self.fields["phone_number"].initial = profile.phone_number

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and user.pk:
            profile = getattr(user, "profile", None)
            if profile:
                profile.callsign = self.cleaned_data["callsign"]
                profile.phone_number = self.cleaned_data["phone_number"]
                profile.save(update_fields=["callsign", "phone_number"])
        return user


class AvatarForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("avatar",)
