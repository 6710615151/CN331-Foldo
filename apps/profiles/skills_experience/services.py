"""
Writes for skills and experience (FOLDO-04).

Each function takes ``cleaned_data`` from a validated form. Views never save
these models themselves, and the owning profile always comes from the caller
(never from user input).
"""

from django.db import transaction

from ..models import Experience, Skill

SKILL_FIELDS = ("name", "proficiency")
EXPERIENCE_FIELDS = ("company", "job_title", "description", "start_date", "end_date")


def _pick(data, fields):
    return {field: data[field] for field in fields if field in data}


@transaction.atomic
def create_skill(*, profile, data) -> Skill:
    return Skill.objects.create(profile=profile, **_pick(data, SKILL_FIELDS))


@transaction.atomic
def update_skill(*, skill, data) -> Skill:
    for field, value in _pick(data, SKILL_FIELDS).items():
        setattr(skill, field, value)
    skill.save()
    return skill


@transaction.atomic
def delete_skill(*, skill) -> None:
    skill.delete()


@transaction.atomic
def create_experience(*, profile, data) -> Experience:
    return Experience.objects.create(profile=profile, **_pick(data, EXPERIENCE_FIELDS))


@transaction.atomic
def update_experience(*, experience, data) -> Experience:
    for field, value in _pick(data, EXPERIENCE_FIELDS).items():
        setattr(experience, field, value)
    experience.save()
    return experience


@transaction.atomic
def delete_experience(*, experience) -> None:
    experience.delete()
