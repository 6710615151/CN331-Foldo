"""Validation for education entries (FOLDO-04). Fields are listed by name; the profile is never a form field."""

import datetime

from django import forms

from apps.core.forms import BootstrapFormMixin

from ..models import Education

# Earliest start date we accept; anything older is almost certainly a typo.
EARLIEST_START = datetime.date(1900, 1, 1)
# How far ahead an expected graduation date may be.
MAX_YEARS_AHEAD = 10


def _today():
    return datetime.date.today()


def _squash(value):
    """Trim and collapse runs of whitespace, so "  KMUTT  " and "KMUTT" are the same."""
    return " ".join((value or "").split())


class EducationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Education
        fields = [
            "institution",
            "degree",
            "field_of_study",
            "start_date",
            "end_date",
            "grade",
            "description",
        ]
        labels = {
            "institution": "สถาบัน (โรงเรียน / มหาวิทยาลัย)",
            "degree": "วุฒิการศึกษา",
            "field_of_study": "สาขาวิชา",
            "start_date": "วันที่เริ่ม",
            "end_date": "วันที่จบ",
            "grade": "เกรด / GPA",
            "description": "รายละเอียด",
        }
        help_texts = {
            "degree": "ไม่บังคับ เช่น “B.Eng.” หรือ “มัธยมปลาย”",
            "field_of_study": "ไม่บังคับ เช่น “วิศวกรรมคอมพิวเตอร์”",
            "end_date": "เว้นว่างถ้ายังเรียนอยู่ ใส่วันในอนาคตได้ถ้าเป็นวันที่คาดว่าจะจบ",
            "grade": "ไม่บังคับ เช่น “3.75” หรือ “เกียรตินิยมอันดับ 1”",
            "description": "ไม่บังคับ: กิจกรรม รางวัล หัวข้อวิทยานิพนธ์",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, profile, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile

    def clean_institution(self):
        value = _squash(self.cleaned_data["institution"])
        if not value:
            raise forms.ValidationError("ต้องกรอกชื่อโรงเรียนหรือมหาวิทยาลัย")
        return value

    def clean_degree(self):
        return _squash(self.cleaned_data["degree"])

    def clean_field_of_study(self):
        return _squash(self.cleaned_data["field_of_study"])

    def clean_grade(self):
        return _squash(self.cleaned_data["grade"])

    def clean_description(self):
        return self.cleaned_data["description"].strip()

    def clean_start_date(self):
        start = self.cleaned_data["start_date"]
        if start < EARLIEST_START:
            raise forms.ValidationError("วันที่เริ่มเก่าเกินไป ตรวจปีอีกครั้ง (ใช้ปี ค.ศ. เช่น 2022)")
        if start > _today():
            raise forms.ValidationError("วันที่เริ่มต้องไม่อยู่ในอนาคต")
        return start

    def clean_end_date(self):
        end = self.cleaned_data["end_date"]
        if end is not None and end.year > _today().year + MAX_YEARS_AHEAD:
            raise forms.ValidationError(f"วันที่จบต้องไม่เกิน {MAX_YEARS_AHEAD} ปีจากนี้")
        return end

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "วันที่จบต้องไม่อยู่ก่อนวันที่เริ่ม")
        return cleaned
