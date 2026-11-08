"""Tests for the ``profiles`` app (FOLDO-03 Main Profile)."""

import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import MAX_PROFILES_PER_USER, MainProfile
from .services import build_display, get_default_profile, get_profile

PASSWORD = "pw-Foldo-12345"


def make_user(username):
    return get_user_model().objects.create_user(username=username, password=PASSWORD)


def make_profile(owner, **fields):
    fields.setdefault("label", "Main profile")
    fields.setdefault("full_name", owner.username.title())
    return MainProfile.objects.create(owner=owner, **fields)


def profile_form_data(**overrides):
    data = {
        "label": "Main profile",
        "full_name": "Alice Example",
        "headline": "Backend developer",
        "bio": "",
        "location": "Bangkok",
        "contact_email": "alice@example.com",
        "phone": "",
        "website": "",
        "linkedin_url": "",
        "github_url": "",
    }
    data.update(overrides)
    return data


def png_bytes(size=(8, 8)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "blue").save(buffer, format="PNG")
    return buffer.getvalue()


class ProfileTestCase(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.client.force_login(self.alice)

    def message_levels(self, response):
        return [m.level_tag for m in get_messages(response.wsgi_request)]


class AccessControlTests(ProfileTestCase):
    """Owner → 200, another user → 404, not signed in → login (docs/CONVENTIONS.md §6)."""

    def setUp(self):
        super().setUp()
        self.own = make_profile(self.alice)
        self.others = make_profile(self.bob)

    def private_urls(self, profile):
        return [
            reverse("profiles:view", args=[profile.pk]),
            reverse("profiles:update", args=[profile.pk]),
            reverse("profiles:delete", args=[profile.pk]),
        ]

    def test_owner_can_open_their_own_profile_pages(self):
        for url in self.private_urls(self.own) + [reverse("profiles:list"), reverse("profiles:create")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_another_users_profile_is_404_not_403(self):
        for url in self.private_urls(self.others):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_visitor_is_redirected_to_login(self):
        self.client.logout()
        login = reverse("accounts:login")
        for url in self.private_urls(self.own) + [reverse("profiles:list"), reverse("profiles:create")]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{login}?next={url}", fetch_redirect_response=False)

    def test_cannot_edit_another_users_profile(self):
        url = reverse("profiles:update", args=[self.others.pk])
        response = self.client.post(url, profile_form_data(full_name="Hacked"))
        self.assertEqual(response.status_code, 404)
        self.others.refresh_from_db()
        self.assertEqual(self.others.full_name, "Bob")

    def test_cannot_delete_another_users_profile(self):
        response = self.client.post(reverse("profiles:delete", args=[self.others.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(MainProfile.objects.filter(pk=self.others.pk).exists())

    def test_cannot_make_another_users_profile_default(self):
        response = self.client.post(reverse("profiles:make_default", args=[self.others.pk]))
        self.assertEqual(response.status_code, 404)

    def test_list_only_shows_own_profiles(self):
        response = self.client.get(reverse("profiles:list"))
        self.assertEqual(list(response.context["profiles"]), [self.own])

    def test_make_default_rejects_get(self):
        response = self.client.get(reverse("profiles:make_default", args=[self.own.pk]))
        self.assertEqual(response.status_code, 405)


class CreateAndEditTests(ProfileTestCase):
    def test_create_saves_profile_for_signed_in_user(self):
        response = self.client.post(reverse("profiles:create"), profile_form_data())
        profile = MainProfile.objects.get(owner=self.alice)
        self.assertRedirects(response, reverse("profiles:view", args=[profile.pk]))
        self.assertEqual(profile.full_name, "Alice Example")
        self.assertTrue(profile.is_default)
        self.assertIn("success", self.message_levels(response))

    def test_owner_comes_from_session_not_form(self):
        self.client.post(reverse("profiles:create"), profile_form_data(owner=self.bob.pk))
        self.assertEqual(MainProfile.objects.get().owner, self.alice)
        self.assertFalse(MainProfile.objects.filter(owner=self.bob).exists())

    def test_edit_updates_and_persists_after_logging_in_again(self):
        profile = make_profile(self.alice)
        self.client.post(
            reverse("profiles:update", args=[profile.pk]),
            profile_form_data(full_name="Alice Updated", headline="Data engineer"),
        )
        self.client.logout()
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.get(reverse("profiles:view", args=[profile.pk]))
        self.assertContains(response, "Alice Updated")
        self.assertContains(response, "Data engineer")

    def test_missing_full_name_is_rejected_and_input_is_kept(self):
        response = self.client.post(
            reverse("profiles:create"), profile_form_data(full_name="", headline="Keep me")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MainProfile.objects.exists())
        self.assertIn("full_name", response.context["form"].errors)
        self.assertContains(response, "Keep me")
        self.assertIn("danger", self.message_levels(response))
        self.assertNotIn("success", self.message_levels(response))

    def test_error_message_uses_bootstrap_danger_alert(self):
        response = self.client.post(reverse("profiles:create"), profile_form_data(full_name=""))
        self.assertContains(response, "alert-danger")
        self.assertNotContains(response, "alert-error")

    def test_duplicate_label_for_same_owner_is_rejected(self):
        make_profile(self.alice, label="Backend")
        response = self.client.post(reverse("profiles:create"), profile_form_data(label="backend"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("label", response.context["form"].errors)
        self.assertEqual(MainProfile.objects.filter(owner=self.alice).count(), 1)

    def test_double_submit_does_not_create_two_profiles(self):
        url = reverse("profiles:create")
        self.client.post(url, profile_form_data())
        self.client.post(url, profile_form_data())
        self.assertEqual(MainProfile.objects.filter(owner=self.alice).count(), 1)

    def test_same_label_is_allowed_for_different_users(self):
        make_profile(self.bob, label="Main profile")
        self.client.post(reverse("profiles:create"), profile_form_data(label="Main profile"))
        self.assertTrue(MainProfile.objects.filter(owner=self.alice).exists())

    def test_invalid_email_phone_and_link_are_rejected(self):
        response = self.client.post(
            reverse("profiles:create"),
            profile_form_data(
                contact_email="not-an-email", phone="call me", website="javascript:alert(1)"
            ),
        )
        errors = response.context["form"].errors
        for field in ("contact_email", "phone", "website"):
            with self.subTest(field=field):
                self.assertIn(field, errors)
        self.assertFalse(MainProfile.objects.exists())

    def test_profile_limit_is_enforced(self):
        for i in range(MAX_PROFILES_PER_USER):
            make_profile(self.alice, label=f"Profile {i}")
        response = self.client.post(reverse("profiles:create"), profile_form_data(label="One more"))
        self.assertRedirects(response, reverse("profiles:list"))
        self.assertEqual(MainProfile.objects.filter(owner=self.alice).count(), MAX_PROFILES_PER_USER)

    def test_user_text_is_escaped(self):
        profile = make_profile(self.alice, bio="<script>alert('x')</script>")
        response = self.client.get(reverse("profiles:view", args=[profile.pk]))
        self.assertNotContains(response, "<script>alert")
        self.assertContains(response, "&lt;script&gt;")


class CompletenessTests(ProfileTestCase):
    def test_new_profile_with_only_name_is_incomplete(self):
        profile = make_profile(self.alice)
        self.assertFalse(profile.is_complete)
        self.assertEqual(profile.missing_fields, ["Headline", "Contact email"])
        self.assertEqual(profile.completion_percent, 33)

    def test_profile_with_required_fields_is_complete(self):
        profile = make_profile(self.alice, headline="Dev", contact_email="a@example.com")
        self.assertTrue(profile.is_complete)
        self.assertEqual(profile.completion_percent, 100)

    def test_saving_incomplete_profile_warns_instead_of_success(self):
        response = self.client.post(
            reverse("profiles:create"), profile_form_data(headline="", contact_email=""), follow=True
        )
        self.assertContains(response, "incomplete")
        self.assertIn("warning", [m.level_tag for m in response.context["messages"]])


class DefaultProfileTests(ProfileTestCase):
    def test_only_the_first_profile_is_default(self):
        first = make_profile(self.alice, label="First")
        second = make_profile(self.alice, label="Second")
        first.refresh_from_db()
        self.assertTrue(first.is_default)
        self.assertFalse(second.is_default)

    def test_make_default_switches_the_default(self):
        first = make_profile(self.alice, label="First")
        second = make_profile(self.alice, label="Second")
        self.client.post(reverse("profiles:make_default", args=[second.pk]))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(second.is_default)
        self.assertFalse(first.is_default)

    def test_deleting_the_default_promotes_another_profile(self):
        first = make_profile(self.alice, label="First")
        second = make_profile(self.alice, label="Second")
        self.client.post(reverse("profiles:delete", args=[first.pk]))
        second.refresh_from_db()
        self.assertTrue(second.is_default)

    def test_default_shortcut_redirects_to_create_when_no_profile(self):
        response = self.client.get(reverse("profiles:detail"))
        self.assertRedirects(response, reverse("profiles:create"))


class DeleteTests(ProfileTestCase):
    def test_get_asks_for_confirmation_and_deletes_nothing(self):
        profile = make_profile(self.alice)
        response = self.client.get(reverse("profiles:delete", args=[profile.pk]))
        self.assertContains(response, "Delete this profile?")
        self.assertTrue(MainProfile.objects.filter(pk=profile.pk).exists())

    def test_post_deletes_and_returns_to_list(self):
        profile = make_profile(self.alice)
        response = self.client.post(reverse("profiles:delete", args=[profile.pk]))
        self.assertRedirects(response, reverse("profiles:list"))
        self.assertFalse(MainProfile.objects.filter(pk=profile.pk).exists())


class PhotoUploadTests(ProfileTestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def test_valid_image_is_stored_under_a_random_name(self):
        photo = SimpleUploadedFile("my face.png", png_bytes(), content_type="image/png")
        self.client.post(reverse("profiles:create"), {**profile_form_data(), "photo": photo})
        profile = MainProfile.objects.get(owner=self.alice)
        self.assertTrue(profile.photo.name.startswith(f"profile_photos/user_{self.alice.pk}/"))
        self.assertNotIn("my face", profile.photo.name)

    def test_non_image_file_is_rejected(self):
        fake = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 not an image", content_type="application/pdf")
        response = self.client.post(reverse("profiles:create"), {**profile_form_data(), "photo": fake})
        self.assertIn("photo", response.context["form"].errors)
        self.assertFalse(MainProfile.objects.exists())


class ServiceTests(ProfileTestCase):
    def test_get_profile_never_returns_another_users_profile(self):
        others = make_profile(self.bob)
        self.assertIsNone(get_profile(self.alice, others.pk))

    def test_default_profile_is_none_without_profiles(self):
        self.assertIsNone(get_default_profile(self.alice))

    def test_display_is_safe_without_a_profile(self):
        display = build_display(self.alice)
        self.assertFalse(display.exists)
        self.assertEqual(display.display_name, "alice")
        self.assertEqual(display.initials, "A")
