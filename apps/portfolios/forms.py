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
            "title": "ชื่อพอร์ตโฟลิโอ",
            "profile": "โปรไฟล์ที่ใช้แสดง",
            "template_key": "เทมเพลต",
            "is_published": "เผยแพร่พอร์ตโฟลิโอนี้",
        }
        widgets = {"template_key": forms.RadioSelect}
        help_texts = {
            "template_key": "เปลี่ยนได้ทุกเมื่อ ไม่กระทบโปรไฟล์หรือพอร์ตโฟลิโออื่น",
            "title": "ตั้งตามงานที่จะสมัคร เช่น “Backend Intern — Agoda” ชื่อนี้เป็นส่วนหนึ่งของลิงก์สาธารณะ",
            "profile": "แก้โปรไฟล์เมื่อไร พอร์ตโฟลิโอนี้จะเปลี่ยนตามทันที",
            "is_published": "เปิด: ใครมีลิงก์ก็ดูได้ รวมถึงข้อมูลติดต่อในโปรไฟล์ " "ปิด: มีแค่คุณที่ดูได้",
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

        field = self.fields["profile"]
        # Only the owner's own profiles can be chosen, so another user's id is rejected as invalid.
        field.queryset = profile_choices(owner)
        field.required = False
        field.empty_label = "โปรไฟล์หลักของฉัน (เปลี่ยนตามเมื่อเปลี่ยนโปรไฟล์หลัก)"
        field.label_from_instance = lambda p: f"{p.label} (โปรไฟล์หลัก)" if p.is_default else p.label

    def clean_title(self):
        return self.cleaned_data["title"].strip()
