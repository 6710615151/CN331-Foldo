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
            "headline": "หัวข้อแนะนำตัว",
            "bio": "ประวัติย่อ",
            "location": "จังหวัดหรือเมือง",
            "photo": "รูปโปรไฟล์",
            "contact_email": "อีเมลติดต่อ",
            "phone": "เบอร์โทรศัพท์",
        }
        help_texts = {
            "label": "มีแค่คุณที่เห็น เช่น “สาย Backend” หรือ “พอร์ตงานออกแบบ”",
            "headline": "บรรทัดเดียว บอกว่าคุณเป็นใครและสนใจงานแบบไหน "
                        "เช่น “นักศึกษาวิศวะคอมฯ สนใจ Backend และ DevOps”",
            "bio": "2–3 ประโยค เล่าพื้นฐาน จุดเด่น และงานที่กำลังมองหา",
            "location": "ไม่ต้องใส่ที่อยู่เต็ม พอร์ตโฟลิโอที่เผยแพร่จะแสดงข้อความนี้",
            "phone": "ไม่บังคับ ถ้าใส่จะแสดงบนพอร์ตโฟลิโอที่เผยแพร่",
            "photo": f"JPG, PNG, WebP หรือ GIF ขนาดไม่เกิน {MAX_PHOTO_BYTES // (1024 * 1024)} MB",
            "contact_email": "อีเมลที่ผู้รับสมัครใช้ติดต่อคุณ แสดงบนพอร์ตโฟลิโอ ไม่จำเป็นต้องเป็นอีเมลที่ใช้เข้าสู่ระบบ",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        # The model default ("Main profile") is English; new profiles start with a Thai name.
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault("label", "โปรไฟล์ของฉัน")
            if self.initial["label"] == MainProfile._meta.get_field("label").default:
                self.initial["label"] = "โปรไฟล์ของฉัน"

    def clean_label(self):
        label = self.cleaned_data["label"].strip()
        clash = MainProfile.objects.filter(owner=self.owner, label__iexact=label).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("มีโปรไฟล์ชื่อนี้อยู่แล้ว ลองตั้งชื่ออื่น")
        return label

    def clean_contact_email(self):
        return self.cleaned_data["contact_email"].strip().lower()
