"""
Validation layer for the ``accounts`` app.

Never trust user input: every field is cleaned here before it reaches
``services.py``. Django's built-in user forms are bound to ``auth.User``; these
subclasses point them at ``CustomUser`` so the admin (and, later, sign-up)
validate against the right model.
"""

from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser
from .selectors import email_is_taken


class _CleanEmailMixin:
    """Normalise the e-mail and keep it unique across accounts."""

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and email_is_taken(email, exclude_pk=self.instance.pk):
            raise forms.ValidationError("อีเมลนี้ถูกใช้งานแล้ว")
        return email


class CustomUserCreationForm(_CleanEmailMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email")


class CustomUserChangeForm(_CleanEmailMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = ("username", "email", "first_name", "last_name")
