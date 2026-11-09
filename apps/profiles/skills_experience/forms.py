"""Validation for skills and experience (FOLDO-04). Fields are listed by name; the profile is never a form field."""

from django import forms

from apps.core.forms import BootstrapFormMixin

from ..models import Experience, Skill


class SkillForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["name", "proficiency"]
        labels = {"name": "ชื่อทักษะ", "proficiency": "ระดับความชำนาญ"}
        help_texts = {"name": "เช่น Python, Figma, การนำเสนอ"}

    def __init__(self, *args, profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if not name:
            raise forms.ValidationError("Enter a skill name.")
        clash = Skill.objects.filter(profile=self.profile, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("You already have this skill on this profile.")
        return name


class ExperienceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Experience
        fields = ["company", "job_title", "start_date", "end_date", "description"]
        labels = {
            "company": "บริษัท / องค์กร",
            "job_title": "ตำแหน่ง",
            "start_date": "วันที่เริ่ม",
            "end_date": "วันที่สิ้นสุด",
            "description": "สิ่งที่ทำ / ผลงาน",
        }
        help_texts = {"end_date": "เว้นว่างไว้ถ้ายังทำงานที่นี่อยู่"}
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile

    def clean_company(self):
        return self._required_text("company", "Enter the company or organisation.")

    def clean_job_title(self):
        return self._required_text("job_title", "Enter your job title.")

    def _required_text(self, field, message):
        value = " ".join(self.cleaned_data[field].split())
        if not value:
            raise forms.ValidationError(message)
        return value

    def clean_description(self):
        return self.cleaned_data["description"].strip()

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date can't be before the start date.")
        return cleaned
