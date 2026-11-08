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
            "title": "ชื่อเวอร์ชัน",
            "profile": "โปรไฟล์ที่ใช้แสดง",
            "template_key": "Template",
            "is_published": "เผยแพร่พอร์ตโฟลิโอนี้",
        }
        widgets = {"template_key": forms.RadioSelect}
        help_texts = {
            "template_key": "แต่ละเวอร์ชันมีเทมเพลตของตัวเอง "
                            "เปลี่ยนแล้วไม่กระทบโปรไฟล์หรือเวอร์ชันอื่น",
            "title": "ใช้แยกเวอร์ชันของคุณเอง เช่น “สำหรับงาน Backend”",
            "profile": "เลือกโปรไฟล์ของคุณ แก้โปรไฟล์เมื่อไรเวอร์ชันนี้จะอัปเดตตามอัตโนมัติ",
            "is_published": "เปิด = ใครมีลิงก์ก็ดูได้ รวมถึงข้อมูลติดต่อในโปรไฟล์ที่เลือก "
                            "ปิด = มีแค่คุณที่ดูตัวอย่างได้",
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

        field = self.fields["profile"]
        # Only the owner's own profiles can be chosen, so another user's id is rejected as invalid.
        field.queryset = profile_choices(owner)
        field.required = False
        field.empty_label = "ใช้โปรไฟล์ Default ของฉัน"
        field.label_from_instance = lambda p: f"{p.label} (Default)" if p.is_default else p.label

    def clean_title(self):
        return self.cleaned_data["title"].strip()
