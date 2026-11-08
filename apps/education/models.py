from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class EducationEntry(models.Model):
    """
    One education level for one user. A user has at most one entry per level
    (so one education record each for high school, undergraduate, graduate and PhD).
    Every detail is optional; a level with nothing filled in simply has no row.
    """

    class Level(models.TextChoices):
        HIGH_SCHOOL = "high_school", "High school"
        UNDERGRADUATE = "undergraduate", "Undergraduate degree"
        GRADUATE = "graduate", "Graduate degree (Master's)"
        PHD = "phd", "PhD"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="education_entries",
    )
    level = models.CharField(max_length=20, choices=Level.choices)

    institution = models.CharField("School / university", max_length=150, blank=True)
    subject = models.CharField("Subject / field of study", max_length=150, blank=True)
    # Free text on purpose: grading systems differ ("3.75/4.00", "First class", "A", "Distinction").
    grade = models.CharField("Grade", max_length=40, blank=True)
    start_year = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1900), MaxValueValidator(2100)]
    )
    end_year = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1900), MaxValueValidator(2100)]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "education entry"
        verbose_name_plural = "education entries"
        constraints = [
            models.UniqueConstraint(fields=["owner", "level"], name="uniq_education_level_per_owner"),
        ]

    def __str__(self):
        return f"{self.get_level_display()} ({self.owner})"

    @property
    def is_blank(self):
        return not (self.institution or self.subject or self.grade or self.start_year or self.end_year)
