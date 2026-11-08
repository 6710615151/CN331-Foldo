"""
FOLDO-10: shared validation

Use these in forms.py / models.py instead of writing your own checks, so the
same rule applies everywhere.
"""

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

# Only normal web links (http / https). Use this on every field that stores a
safe_url_validator = URLValidator(schemes=["http", "https"])

# Maximum lengths (characters) shared by all apps.
MAX_SHORT_NAME = 100   # display name, skill name
MAX_SHORT_TEXT = 200   # project name, job title, institution
MAX_URL = 500          # any link
MAX_LONG_TEXT = 5000   # bio, description, project story

def validate_date_order(start_date, end_date):
    """Raise ValidationError when end_date is before start_date.

    Either date may be empty (still studying, still working, not finished),
    so the check runs only when both are filled. Use it in a form's clean():

        def clean(self):
            cleaned = super().clean()
            try:
                validate_date_order(cleaned.get("start_date"), cleaned.get("end_date"))
            except ValidationError as error:
                self.add_error("end_date", error)
            return cleaned
    """
    if start_date and end_date and end_date < start_date:
        raise ValidationError(
            "วันที่สิ้นสุดต้องไม่อยู่ก่อนวันที่เริ่ม",
            code="end_before_start",
        )