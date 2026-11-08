import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models, transaction
from django.urls import reverse

from apps.core.validators import (
    MAX_LONG_TEXT,
    MAX_SHORT_TEXT,
    MAX_URL,
    safe_url_validator,
    validate_date_order,
)

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PROFILES_PER_USER = 10

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
    A reusable set of personal information. A user can keep several (up to
    MAX_PROFILES_PER_USER); exactly one of them is their default.
    Portfolio versions should read from these (see profiles.services) rather than copy them.
    """

    # Needed for a profile to count as "complete" / portfolio-ready. Saving without these is allowed.
    REQUIRED_FOR_PORTFOLIO = {
        "full_name": "Full name",
        "headline": "Headline",
        "contact_email": "Contact email",
    }

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="main_profiles",
    )

    # Which profile this is (only the owner sees this name)
    label = models.CharField(max_length=60, default="Main profile")
    is_default = models.BooleanField(default=False)

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
        ordering = ["-is_default", "label"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "label"], name="uniq_profile_label_per_owner"),
            models.UniqueConstraint(
                fields=["owner"],
                condition=models.Q(is_default=True),
                name="uniq_default_profile_per_owner",
            ),
        ]

    def __str__(self):
        return f"{self.label} ({self.owner})"

    def get_absolute_url(self):
        return reverse("profiles:view", args=[self.pk])

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
        old_photo = ""
        if self.pk:
            old_photo = type(self).objects.filter(pk=self.pk).values_list("photo", flat=True).first() or ""

        with transaction.atomic():
            # A user's first profile is always their default.
            if self._state.adding and not type(self).objects.filter(owner_id=self.owner_id).exists():
                self.is_default = True
            # Only one default per owner: demote the others before saving this one.
            if self.is_default:
                type(self).objects.filter(owner_id=self.owner_id, is_default=True).exclude(pk=self.pk).update(
                    is_default=False
                )
            super().save(*args, **kwargs)

        # Remove the replaced / cleared photo file only after the new state is saved.
        new_photo = self.photo.name if self.photo else ""
        if old_photo and old_photo != new_photo:
            try:
                self.photo.storage.delete(old_photo)
            except OSError:
                logger.warning("Could not delete old profile photo %s", old_photo, exc_info=True)

    def delete(self, *args, **kwargs):
        owner_id, was_default = self.owner_id, self.is_default
        photo_name = self.photo.name if self.photo else ""
        storage = self.photo.storage

        with transaction.atomic():
            result = super().delete(*args, **kwargs)
            # If the default was deleted, promote the most recently updated remaining profile.
            if was_default:
                successor = type(self).objects.filter(owner_id=owner_id).order_by("-updated_at").first()
                if successor:
                    successor.is_default = True
                    successor.save(update_fields=["is_default"])

        if photo_name:
            try:
                storage.delete(photo_name)
            except OSError:
                logger.warning("Could not delete profile photo %s", photo_name, exc_info=True)
        return result



class Project(models.Model):
    """One project on a main profile (FOLDO-04) with an optional Project Story (FOLDO-15).

    The five story parts are stored on the project itself, so a project without
    a story (for example one created before FOLDO-15) simply has them blank.
    """

    STORY_FIELDS = ("problem", "role", "process", "solution", "outcome")

    profile = models.ForeignKey(MainProfile, on_delete=models.CASCADE, related_name="projects")
    project_name = models.CharField(max_length=MAX_SHORT_TEXT)
    description = models.TextField(max_length=MAX_LONG_TEXT, blank=True)
    project_url = models.URLField(max_length=MAX_URL, blank=True, validators=[safe_url_validator])
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Project Story (FOLDO-15): every part is optional.
    problem = models.TextField(max_length=MAX_LONG_TEXT, blank=True)
    role = models.TextField(max_length=MAX_LONG_TEXT, blank=True)
    process = models.TextField(max_length=MAX_LONG_TEXT, blank=True)
    solution = models.TextField(max_length=MAX_LONG_TEXT, blank=True)
    outcome = models.TextField(max_length=MAX_LONG_TEXT, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [models.F("start_date").desc(nulls_last=True), "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_date__isnull=True)
                | models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="project_end_not_before_start",
            ),
        ]

    def __str__(self):
        return self.project_name

    def clean(self):
        super().clean()
        try:
            validate_date_order(self.start_date, self.end_date)
        except ValidationError as error:
            raise ValidationError({"end_date": error.messages}) from error

    @property
    def has_story(self):
        return any((getattr(self, name) or "").strip() for name in self.STORY_FIELDS)