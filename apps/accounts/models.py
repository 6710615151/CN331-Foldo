"""
Data layer for the ``accounts`` app.

FOLDO uses a custom user model from the very first migration
(``AUTH_USER_MODEL = "accounts.CustomUser"``) so fields can be added later
without a painful mid-project user-model swap. It deliberately adds nothing
yet: the student's portfolio content will live in a separate profiles app
(FOLDO-02) linked to this model one-to-one.
"""

from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    """A FOLDO account. Extend with fields only when a backlog Issue needs them."""

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.get_username()
