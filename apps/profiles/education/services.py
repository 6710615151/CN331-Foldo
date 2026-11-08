"""
Writes for education (FOLDO-04).

Each function takes ``cleaned_data`` from a validated ``EducationForm``. Views
never save the model themselves, and the owning profile always comes from the
caller (looked up through the signed-in user), never from user input.
"""

from django.db import transaction

from ..models import Education

EDUCATION_FIELDS = (
    "institution",
    "degree",
    "field_of_study",
    "start_date",
    "end_date",
    "grade",
    "description",
)


def _pick(data):
    return {field: data[field] for field in EDUCATION_FIELDS if field in data}


@transaction.atomic
def create_education(*, profile, data) -> Education:
    return Education.objects.create(profile=profile, **_pick(data))


@transaction.atomic
def update_education(*, education, data) -> Education:
    for field, value in _pick(data).items():
        setattr(education, field, value)
    education.save()
    return education


@transaction.atomic
def delete_education(*, education) -> None:
    education.delete()
