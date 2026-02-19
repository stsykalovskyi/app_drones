from django.contrib.auth.models import User
from django.db import models


def avatar_upload_path(instance, filename):
    return f"avatars/{instance.user_id}/{filename}"


class Profile(models.Model):
    """Extended user profile with avatar."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Користувач",
    )
    callsign = models.CharField(
        "Позивний",
        max_length=50,
        blank=True,
    )
    avatar = models.ImageField(
        "Фото",
        upload_to=avatar_upload_path,
        blank=True,
    )

    class Meta:
        verbose_name = "Профіль"
        verbose_name_plural = "Профілі"

    @property
    def display_name(self):
        """Return callsign if set, then full name, then username."""
        return self.callsign or self.user.get_full_name() or self.user.username

    def __str__(self):
        return self.display_name
