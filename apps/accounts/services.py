"""
Business logic layer for the ``accounts`` app (mutations only).

Views call these functions; they never write to the database themselves.
"""

from django.contrib.auth import get_user_model
from django.db import transaction

EDITABLE_FIELDS = ("first_name", "last_name", "email")


@transaction.atomic
def update_account(*, user, data: dict):
    """Apply validated settings to ``user`` and save only the changed fields."""
    current = get_user_model().objects.select_for_update().get(pk=user.pk)
    changed = [
        field for field in EDITABLE_FIELDS
        if field in data and getattr(current, field) != data[field]
    ]
    for field in changed:
        setattr(current, field, data[field])
    if changed:
        current.save(update_fields=changed)
    return current
