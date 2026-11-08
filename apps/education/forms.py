from django import forms

from .models import EducationEntry


class EducationLevelForm(forms.ModelForm):
    """Details for ONE level. Used four times on the settings page, each with its own prefix."""

    class Meta:
        model = EducationEntry
        fields = ["institution", "subject", "grade", "start_year", "end_year"]
        labels = {
            "institution": "School / university",
            "subject": "Subject / field of study",
            "grade": "Grade",
            "start_year": "Start year",
            "end_year": "End year",
        }
        help_texts = {
            "grade": "Any format, e.g. 3.75/4.00, First class, A.",
        }
        widgets = {
            "start_year": forms.NumberInput(attrs={"min": 1900, "max": 2100, "placeholder": "e.g. 2018"}),
            "end_year": forms.NumberInput(attrs={"min": 1900, "max": 2100, "placeholder": "e.g. 2022"}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_year"), cleaned.get("end_year")
        if start and end and end < start:
            self.add_error("end_year", "End year can't be earlier than the start year.")
        return cleaned

    @property
    def is_blank(self):
        """True when every field was left empty (only meaningful after is_valid())."""
        return not any(value not in (None, "") for value in self.cleaned_data.values())
