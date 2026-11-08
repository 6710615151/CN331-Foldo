"""Validation for education entries (FOLDO-04). Fields are listed by name; the profile is never a form field."""

import datetime

from django import forms

from apps.core.forms import BootstrapFormMixin

from ..models import Education

# Earliest start date we accept; anything older is almost certainly a typo.
EARLIEST_START = datetime.date(1900, 1, 1)
# How far ahead an expected graduation date may be.
MAX_YEARS_AHEAD = 10


def _today():
    return datetime.date.today()


def _squash(value):
    """Trim and collapse runs of whitespace, so "  KMUTT  " and "KMUTT" are the same."""
    return " ".join((value or "").split())


class EducationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Education
        fields = [
            "institution",
            "degree",
            "field_of_study",
            "start_date",
            "end_date",
            "grade",
            "description",
        ]
        labels = {
            "institution": "School / university",
            "degree": "Degree",
            "field_of_study": "Field of study",
            "start_date": "Start date",
            "end_date": "End date",
            "grade": "Grade / GPA",
            "description": "Details",
        }
        help_texts = {
            "degree": "Optional, e.g. \"B.Eng.\" or \"High school diploma\".",
            "field_of_study": "Optional, e.g. \"Computer Engineering\".",
            "end_date": "Leave empty if you are still studying here. A future date means expected graduation.",
            "grade": "Optional, e.g. \"3.75\" or \"First-class honours\".",
            "description": "Optional: activities, awards, thesis topic.",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile

    def clean_institution(self):
        value = _squash(self.cleaned_data["institution"])
        if not value:
            raise forms.ValidationError("Enter the school or university name.")
        return value

    def clean_degree(self):
        return _squash(self.cleaned_data["degree"])

    def clean_field_of_study(self):
        return _squash(self.cleaned_data["field_of_study"])

    def clean_grade(self):
        return _squash(self.cleaned_data["grade"])

    def clean_description(self):
        return self.cleaned_data["description"].strip()

    def clean_start_date(self):
        start = self.cleaned_data["start_date"]
        if start < EARLIEST_START:
            raise forms.ValidationError("Start date looks too early. Please check the year.")
        if start > _today():
            raise forms.ValidationError("Start date can't be in the future.")
        return start

    def clean_end_date(self):
        end = self.cleaned_data["end_date"]
        if end is not None and end.year > _today().year + MAX_YEARS_AHEAD:
            raise forms.ValidationError(f"End date can be at most {MAX_YEARS_AHEAD} years from now.")
        return end

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date can't be before the start date.")
        return cleaned
