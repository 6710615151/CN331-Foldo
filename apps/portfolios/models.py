import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Portfolio(models.Model):
    """
    A portfolio version: a layout plus a choice of which of the owner's profiles to show.

    It only *references* the profile (it never copies it), so editing the profile
    updates every portfolio that uses it.
    """

    # To add a layout: add a choice here and a file portfolios/layouts/<key>.html
    TEMPLATE_CHOICES = [
        ("classic", "Classic (light)"),
        ("midnight", "Midnight (dark)"),
        ("ocean", "Ocean (blue)"),
        ("mono", "Mono (black & white)"),
    ]
    DEFAULT_TEMPLATE = "classic"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True, blank=True, editable=False)

    # Empty = "follow my default profile". If the chosen profile is deleted this falls back to that too.
    profile = models.ForeignKey(
        "profiles.MainProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portfolios",
    )
    template_key = models.CharField(max_length=40, choices=TEMPLATE_CHOICES, default=DEFAULT_TEMPLATE)

    # Off by default: nothing is visible to anyone but the owner until they publish.
    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} ({self.owner})"

    def get_absolute_url(self):
        return reverse("portfolios:preview", args=[self.pk])

    @property
    def public_path(self):
        return reverse("portfolios:public", args=[self.slug])

    def _make_slug(self):
        base = slugify(self.title)[:60] or "portfolio"
        # Random suffix keeps public links unguessable and collision-free.
        while True:
            slug = f"{base}-{uuid.uuid4().hex[:6]}"
            if not type(self).objects.filter(slug=slug).exists():
                return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._make_slug()
        super().save(*args, **kwargs)
