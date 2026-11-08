from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.core.validators import safe_url_validator

from .models import MAX_PHOTO_BYTES, MainProfile


def _link_field(label):
    # assume_scheme lets users type "example.com" instead of "https://example.com".
    # max_length matches the model's URLField (200); safe_url_validator allows only http/https.
    return forms.URLField(
        label=label,
        required=False,
        max_length=200,
        assume_scheme="https",
        validators=[safe_url_validator],
    )


class MainProfileForm(BootstrapFormMixin, forms.ModelForm):
    website = _link_field("Website")
    linkedin_url = _link_field("LinkedIn")
    github_url = _link_field("GitHub")

    class Meta:
        model = MainProfile
        fields = [
            "label",
            "full_name",
            "headline",
            "bio",
            "location",
            "photo",
            "contact_email",
            "phone",
            "website",
            "linkedin_url",
            "github_url",
        ]
        labels = {
            "label": "Profile name",
            "full_name": "Full name",
            "headline": "Headline",
            "bio": "About you",
            "location": "Location",
            "photo": "Profile photo",
            "contact_email": "Contact email",
            "phone": "Phone",
        }
        help_texts = {
            "label": "Only you see this, e.g. \"Backend developer\" or \"Design portfolio\".",
            "headline": "One line, e.g. \"Backend developer and DevOps enthusiast\".",
            "photo": f"JPG, PNG, WebP or GIF, up to {MAX_PHOTO_BYTES // (1024 * 1024)} MB.",
            "contact_email": "Shown on your portfolios. Can differ from your login email.",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_label(self):
        label = self.cleaned_data["label"].strip()
        clash = MainProfile.objects.filter(owner=self.owner, label__iexact=label).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("You already have a profile with this name.")
        return label

    def clean_contact_email(self):
        return self.cleaned_data["contact_email"].strip().lower()
