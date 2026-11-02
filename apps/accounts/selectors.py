"""
Data access layer for the ``accounts`` app (pure reads, no side effects).

Use ``select_related`` / ``prefetch_related`` here when a query follows
relations, and ``only()`` / ``values()`` when only a few fields are needed.
"""

from django.contrib.auth import get_user_model


def email_is_taken(email: str, *, exclude_pk=None) -> bool:
    """True if another account already uses ``email`` (case-insensitive)."""
    users = get_user_model().objects.filter(email__iexact=email)
    if exclude_pk is not None:
        users = users.exclude(pk=exclude_pk)
    return users.exists()


def get_account(pk):
    """Fresh copy of account ``pk``, so form validation never mutates ``request.user``."""
    return get_user_model().objects.get(pk=pk)
