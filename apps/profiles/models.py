import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.urls import reverse

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB

phone_validator = RegexValidator(
    regex=r"^\+?[0-9 ()\-.]{6,32}$",
    message="Enter a valid phone number (digits, spaces, + ( ) - . only).",
)


def profile_photo_path(instance, filename):
    """Random file name, namespaced per owner, so uploads never collide or leak original names."""
    ext = Path(filename).suffix.lower()
    return f"profile_photos/user_{instance.owner_id}/{uuid.uuid4().hex}{ext}"


def validate_photo_size(file):
    if file.size > MAX_PHOTO_BYTES:
        raise ValidationError(f"Photo is too large (max {MAX_PHOTO_BYTES // (1024 * 1024)} MB).")


class MainProfile(models.Model):
    """
    The single, reusable source of truth for a user's information.
    Portfolio versions should read from this (see profiles.services) rather than copy it.
    """

    # Minimum needed to SAVE a profile.
    REQUIRED_TO_SAVE = ("full_name",)
    # Needed for a profile to count as "complete" / portfolio-ready. Saving without these is allowed.
    REQUIRED_FOR_PORTFOLIO = {
        "full_name": "Full name",
        "headline": "Headline",
        "contact_email": "Contact email",
    }

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="main_profile",
    )

    # Basic info
    full_name = models.CharField(max_length=120)
    headline = models.CharField(max_length=160, blank=True)
    bio = models.TextField(max_length=2000, blank=True)
    location = models.CharField(max_length=120, blank=True)
    photo = models.ImageField(
        upload_to=profile_photo_path,
        blank=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp", "gif"]),
            validate_photo_size,
        ],
    )

    # Contact
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True, validators=[phone_validator])

    # Links
    website = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "main profile"

    def __str__(self):
        return f"Main profile of {self.owner}"

    def get_absolute_url(self):
        return reverse("profiles:detail")

    # --- completeness -------------------------------------------------
    @property
    def missing_fields(self):
        """Human labels of portfolio-required fields that are still empty."""
        return [
            label
            for name, label in self.REQUIRED_FOR_PORTFOLIO.items()
            if not (getattr(self, name, "") or "").strip()
        ]

    @property
    def is_complete(self):
        return not self.missing_fields

    @property
    def completion_percent(self):
        total = len(self.REQUIRED_FOR_PORTFOLIO)
        return int(100 * (total - len(self.missing_fields)) / total)

    # --- persistence --------------------------------------------------
    def save(self, *args, **kwargs):
        old_photo = None
        if self.pk:
            old_photo = type(self).objects.filter(pk=self.pk).values_list("photo", flat=True).first()

        super().save(*args, **kwargs)

        # Remove the replaced / cleared photo file only after the new state is saved.
        new_photo = self.photo.name if self.photo else ""
        if old_photo and old_photo != new_photo:
            try:
                self.photo.storage.delete(old_photo)
            except OSError:
                logger.warning("Could not delete old profile photo %s", old_photo, exc_info=True)
