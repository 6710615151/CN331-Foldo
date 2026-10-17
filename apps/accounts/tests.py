"""Tests for the ``accounts`` app: custom user model, selectors and forms."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import CustomUser


class CustomUserModelTests(TestCase):
    def test_custom_user_is_the_auth_user_model(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.CustomUser")
        self.assertIs(get_user_model(), CustomUser)

    def test_create_user_hashes_the_password(self):
        user = get_user_model().objects.create_user(
            username="student", email="student@example.com", password="s3cret-pass"
        )
        self.assertTrue(user.check_password("s3cret-pass"))
        self.assertNotEqual(user.password, "s3cret-pass")
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        admin = get_user_model().objects.create_superuser(
            username="instructor", email="instructor@example.com", password="s3cret-pass"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


class EmailSelectorTests(TestCase):
    def test_email_is_taken_ignores_case_and_can_exclude_self(self):
        from .selectors import email_is_taken

        user = get_user_model().objects.create_user(
            username="a", email="a@example.com", password="s3cret-pass"
        )
        self.assertTrue(email_is_taken("A@Example.com"))
        self.assertFalse(email_is_taken("a@example.com", exclude_pk=user.pk))
        self.assertFalse(email_is_taken("b@example.com"))


class CreationFormTests(TestCase):
    def _form(self, email):
        from .forms import CustomUserCreationForm

        return CustomUserCreationForm(
            data={"username": "new", "email": email,
                  "password1": "Long-enough-pass-42", "password2": "Long-enough-pass-42"}
        )

    def test_email_is_normalised(self):
        form = self._form("  New.User@Example.COM ")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "new.user@example.com")

    def test_duplicate_email_is_rejected(self):
        get_user_model().objects.create_user(
            username="taken", email="taken@example.com", password="s3cret-pass"
        )
        form = self._form("TAKEN@example.com")
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
