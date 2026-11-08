from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.rendering.themes import THEMES

from .models import Portfolio
from .services import profile_choices


class PortfolioForm(BootstrapFormMixin, forms.ModelForm):
    # Shown as cards by rendering/partials/theme_picker.html (FOLDO-07).
    themes = THEMES

    class Meta:
        model = Portfolio
        fields = ["title", "profile", "template_key", "is_published"]
        labels = {
            "title": "Portfolio title",
            "profile": "Profile to show",
            "template_key": "Template",
            "is_published": "Publish this portfolio",
        }
        widgets = {"template_key": forms.RadioSelect}
        help_texts = {
            "template_key": "Each portfolio version keeps its own template. "
                            "Changing it never changes your profile or your other versions.",
            "title": "Only used to tell your portfolios apart, e.g. \"For backend jobs\".",
            "profile": "Pick one of your profiles. Changes you make to it show up here automatically.",
            "is_published": "When on, anyone with the link can see this portfolio, including the "
                            "contact details of the chosen profile. When off, only you can preview it.",
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

        field = self.fields["profile"]
        # Only the owner's own profiles can be chosen, so another user's id is rejected as invalid.
        field.queryset = profile_choices(owner)
        field.required = False
        field.empty_label = "Use my default profile"
        field.label_from_instance = lambda p: f"{p.label} (default)" if p.is_default else p.label

    def clean_title(self):
        return self.cleaned_data["title"].strip()
