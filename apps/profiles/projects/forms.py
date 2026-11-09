"""Validation for projects and Project Story (FOLDO-04, FOLDO-15). The profile is never a form field."""

from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.core.validators import MAX_URL, safe_url_validator

from ..models import Project


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    # assume_scheme lets users type "github.com/me/app"; only http/https links are accepted.
    project_url = forms.URLField(
        label="ลิงก์โปรเจกต์",
        required=False,
        max_length=MAX_URL,
        assume_scheme="https",
        validators=[safe_url_validator],
        help_text="GitHub, เดโม หรือบทความเล่าโปรเจกต์",
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
            "project_name": "ชื่อโปรเจกต์",
            "description": "คำอธิบายสั้น ๆ",
            "start_date": "วันที่เริ่ม",
            "end_date": "วันที่สิ้นสุด",
            "problem": "ปัญหา",
            "role": "บทบาทของคุณ",
            "process": "วิธีทำ",
            "solution": "ทางออก",
            "outcome": "ผลลัพธ์",
        }
        help_texts = {
            "description": "1–2 ประโยค ว่าโปรเจกต์นี้คืออะไร ใช้ทำอะไร",
            "end_date": "เว้นว่างถ้ายังทำอยู่",
            "problem": "โปรเจกต์นี้แก้ปัญหาอะไร ให้ใคร",
            "role": "คุณรับผิดชอบส่วนไหน",
            "process": "ทำอย่างไร ใช้เครื่องมือหรือวิธีไหน",
            "solution": "สร้างหรือตัดสินใจอะไรออกมา",
            "outcome": "เกิดผลอะไรขึ้น ถ้ามีตัวเลข เช่น จำนวนผู้ใช้ เวลาที่ลดลง ให้ใส่ด้วย",
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
        # required=True + strip=True already reject blank input before this runs.
        return " ".join(self.cleaned_data["project_name"].split())
