"""Validation for projects and Project Story (FOLDO-04, FOLDO-15). The profile is never a form field."""

from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.core.validators import MAX_URL, safe_url_validator

from ..models import Project


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    # assume_scheme lets users type "github.com/me/app"; only http/https links are accepted.
    project_url = forms.URLField(
        label="Project link",
        required=False,
        max_length=MAX_URL,
        assume_scheme="https",
        validators=[safe_url_validator],
        help_text="GitHub, live demo or write-up.",
    )

    class Meta:
        model = Project
        fields = [
            "project_name",
            "description",
            "project_url",
            "start_date",
            "end_date",
            # Project Story (FOLDO-15): all optional
            "problem",
            "role",
            "process",
            "solution",
            "outcome",
        ]
        labels = {
            "project_name": "Project name",
            "description": "Short description",
            "start_date": "Start date",
            "end_date": "End date",
            "problem": "Problem",
            "role": "Role",
            "process": "Process",
            "solution": "Solution",
            "outcome": "Outcome",
        }
        help_texts = {
            "end_date": "Leave empty if the project is still going.",
            "problem": "What problem did the project solve?",
            "role": "What was your part in it?",
            "process": "How did you work on it?",
            "solution": "What did you build or decide?",
            "outcome": "What changed because of it? Numbers help.",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
            "problem": forms.Textarea(attrs={"rows": 3}),
            "role": forms.Textarea(attrs={"rows": 3}),
            "process": forms.Textarea(attrs={"rows": 3}),
            "solution": forms.Textarea(attrs={"rows": 3}),
            "outcome": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_project_name(self):
        name = " ".join(self.cleaned_data["project_name"].split())
        if not name:
            raise forms.ValidationError("Enter a project name.")
        return name