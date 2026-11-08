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


class PortfolioContentSetup(models.Model):
    """
    Marks a portfolio whose owner has chosen its content (FOLDO-06).

    No row = "never customised", and the portfolio shows everything from its profile.
    A row with no PortfolioContentSelection rows = "customised to show nothing".
    """

    portfolio = models.OneToOneField(Portfolio, on_delete=models.CASCADE, related_name="content_setup")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Content chosen for {self.portfolio_id}"


class PortfolioContentSelection(models.Model):
    """
    One piece of profile content included in one portfolio version.

    It only references the source row by section + item_id (it never copies it).
    item_id is deliberately not a foreign key: one table serves education, skills,
    experience and projects, and deleting a source row can never be blocked by (or silently
    cascade into) a portfolio. Rows whose source has gone are ignored when reading and are
    removed the next time the selection is saved.
    """

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="content_selections")
    section = models.CharField(max_length=20)
    item_id = models.PositiveIntegerField()

    class Meta:
        ordering = ["section", "item_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "section", "item_id"], name="uniq_selection_per_portfolio_item"
            ),
        ]

    def __str__(self):
        return f"{self.section}:{self.item_id} in {self.portfolio_id}"
