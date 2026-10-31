"""Tests for the ``accounts`` app: custom user model, selectors and forms."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import services
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


class AccountSettingsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="s3cret-pass",
            first_name="Alice", last_name="Anderson",
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="s3cret-pass",
            first_name="Bobby", last_name="Brown",
        )
        self.url = reverse("accounts:settings")
        self.client.force_login(self.alice)

    def _post(self, **overrides):
        data = {"first_name": "Alice", "last_name": "Anderson", "email": "alice@example.com"}
        data.update(overrides)
        return self.client.post(self.url, data)

    def _assert_alice_unchanged(self):
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@example.com")
        self.assertEqual(self.alice.first_name, "Alice")

    def test_anonymous_get_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(
            response, f"{settings.LOGIN_URL}?next={self.url}", fetch_redirect_response=False
        )

    def test_anonymous_post_redirects_and_changes_nothing(self):
        self.client.logout()
        response = self._post(email="hacked@example.com", first_name="Hacked")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(settings.LOGIN_URL))
        self._assert_alice_unchanged()

    def test_get_shows_own_account(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/settings.html")
        self.assertContains(response, "alice")
        self.assertContains(response, "alice@example.com")

    def test_get_does_not_show_other_users_data(self):
        response = self.client.get(self.url)
        for leaked in ("bob", "bob@example.com", "Bobby", "Brown"):
            self.assertNotContains(response, leaked)

    def test_post_only_changes_own_account(self):
        response = self._post(first_name="Alicia", email="alicia@example.com")
        self.assertRedirects(response, self.url)
        self.alice.refresh_from_db()
        self.bob.refresh_from_db()
        self.assertEqual(self.alice.first_name, "Alicia")
        self.assertEqual(self.alice.email, "alicia@example.com")
        self.assertEqual(
            (self.bob.username, self.bob.email, self.bob.first_name, self.bob.last_name),
            ("bob", "bob@example.com", "Bobby", "Brown"),
        )

    def test_url_cannot_target_another_user(self):
        self.assertEqual(reverse("accounts:settings"), "/accounts/settings/")
        self.assertEqual(self.client.get(f"{self.url}{self.bob.pk}/").status_code, 404)

    def test_valid_post_redirects_with_success_message(self):
        response = self._post(last_name="Smith")
        self.assertRedirects(response, self.url)
        self.assertEqual(
            [str(m) for m in get_messages(response.wsgi_request)],
            ["บันทึกการตั้งค่าเรียบร้อยแล้ว"],
        )
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.last_name, "Smith")

    def test_duplicate_email_is_rejected_case_insensitively(self):
        response = self._post(email="BOB@Example.com", first_name="Changed")
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(
            [str(m) for m in get_messages(response.wsgi_request)],
            ["กรุณาตรวจสอบข้อมูลที่กรอกอีกครั้ง"],
        )
        self._assert_alice_unchanged()

    def test_blank_or_malformed_email_is_rejected(self):
        for bad in ("", "not-an-email"):
            with self.subTest(email=bad):
                response = self._post(email=bad)
                self.assertEqual(response.status_code, 200)
                self.assertIn("email", response.context["form"].errors)
        self._assert_alice_unchanged()

    def test_keeping_own_email_is_valid(self):
        self.assertRedirects(self._post(), self.url)

    def test_email_is_normalised(self):
        self._post(email="  Alice@EXAMPLE.com ")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@example.com")

    def test_username_and_privilege_fields_are_ignored(self):
        self._post(username="mallory", is_staff="on", is_superuser="on")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.username, "alice")
        self.assertFalse(self.alice.is_staff)
        self.assertFalse(self.alice.is_superuser)

    def test_template_has_loading_hook_and_csrf(self):
        response = self.client.get(self.url)
        self.assertContains(response, "data-loading")
        self.assertContains(response, "csrfmiddlewaretoken")


class UpdateAccountServiceTests(TestCase):
    def test_saves_only_changed_fields(self):
        user = get_user_model().objects.create_user(
            username="carol", email="carol@example.com", password="s3cret-pass",
            first_name="Carol", last_name="Clark",
        )
        data = {"first_name": "Carol", "last_name": "Clarke", "email": "carol@example.com"}
        with CaptureQueriesContext(connection) as queries:
            services.update_account(user=user, data=data)
        updates = [q["sql"] for q in queries if q["sql"].startswith("UPDATE")]
        self.assertEqual(len(updates), 1)
        self.assertIn("last_name", updates[0])
        self.assertNotIn("first_name", updates[0])
        self.assertNotIn('"email"', updates[0])
        user.refresh_from_db()
        self.assertEqual(user.last_name, "Clarke")

    def test_no_changes_issues_no_update(self):
        user = get_user_model().objects.create_user(
            username="dave", email="dave@example.com", password="s3cret-pass"
        )
        with CaptureQueriesContext(connection) as queries:
            services.update_account(
                user=user, data={"first_name": "", "last_name": "", "email": "dave@example.com"}
            )
        self.assertFalse([q for q in queries if q["sql"].startswith("UPDATE")])
