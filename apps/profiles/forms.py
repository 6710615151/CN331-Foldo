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
    website = _link_field("เว็บไซต์")
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
            "label": "ชื่อโปรไฟล์",
            "full_name": "ชื่อ-นามสกุล",
            "headline": "หัวข้อแนะนำตัว (Headline)",
            "bio": "ประวัติย่อ",
            "location": "ที่อยู่ / จังหวัด",
            "photo": "รูปโปรไฟล์",
            "contact_email": "อีเมลติดต่อ",
            "phone": "เบอร์โทรศัพท์",
        }
        help_texts = {
            "label": "มีแค่คุณที่เห็น เช่น “สาย Backend” หรือ “พอร์ตงานออกแบบ”",
            "headline": "หนึ่งบรรทัด เช่น “นักศึกษาวิศวะคอมฯ สนใจ Backend และ DevOps”",
            "photo": f"JPG, PNG, WebP หรือ GIF ขนาดไม่เกิน {MAX_PHOTO_BYTES // (1024 * 1024)} MB",
            "contact_email": "แสดงบนพอร์ตโฟลิโอ ใช้คนละอีเมลกับที่ใช้เข้าสู่ระบบได้",
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
