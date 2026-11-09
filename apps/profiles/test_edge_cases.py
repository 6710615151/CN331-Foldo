"""Edge cases and failure paths for profiles: blank-but-not-empty input, photo
limits and cleanup, unique-name races, and database errors on save/delete."""

import datetime
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import DatabaseError, IntegrityError
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.profiles import services
from apps.profiles.education.forms import EducationForm
from apps.profiles.forms import MainProfileForm
from apps.profiles.models import MAX_PHOTO_BYTES, Education, Experience, MainProfile, Skill, validate_photo_size
from apps.profiles.projects.forms import ProjectForm
from apps.profiles.skills_experience.forms import ExperienceForm, SkillForm

PASSWORD = "pw-Foldo-12345"


class _Owner(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="owner", password=PASSWORD)
        self.profile = MainProfile.objects.create(owner=self.user, label="Main", full_name="Owner")
        self.client.force_login(self.user)

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class ModelTests(_Owner):
    def test_string_forms_and_urls(self):
        self.assertEqual(str(self.profile), "Main (owner)")
        self.assertEqual(self.profile.get_absolute_url(), reverse("profiles:view", args=[self.profile.pk]))
        start = datetime.date(2020, 1, 1)
        self.assertEqual(str(Education(profile=self.profile, institution="KU", start_date=start)), "KU")
        self.assertEqual(
            str(Education(profile=self.profile, institution="KU", degree="B.Eng.", start_date=start)), "B.Eng. at KU"
        )

    def test_photos_over_the_limit_are_rejected(self):
        validate_photo_size(mock.Mock(size=MAX_PHOTO_BYTES))
        with self.assertRaises(ValidationError):
            validate_photo_size(mock.Mock(size=MAX_PHOTO_BYTES + 1))


class PhotoCleanupTests(_Owner):
    """Removing an old photo file can fail (disk, permissions); the save must still succeed."""

    def test_replace_and_delete_survive_storage_errors(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.profile.photo.save("a.png", ContentFile(b"first"))
            from django.core.files.storage import FileSystemStorage as storage_class

            with (
                mock.patch.object(storage_class, "delete", side_effect=OSError),
                self.assertLogs("apps.profiles.models", "WARNING"),
            ):
                self.profile.photo.save("b.png", ContentFile(b"second"))
            self.profile.refresh_from_db()
            self.assertTrue(self.profile.photo.name.endswith(".png"))

            with (
                mock.patch.object(storage_class, "delete", side_effect=OSError),
                self.assertLogs("apps.profiles.models", "WARNING"),
            ):
                self.profile.delete()
            self.assertFalse(MainProfile.objects.filter(pk=self.profile.pk).exists())


class ServiceTests(_Owner):
    def test_anonymous_users_have_no_profiles(self):
        self.assertFalse(services.get_profiles(AnonymousUser()).exists())

    def test_get_profile_without_an_id_is_the_default(self):
        self.assertEqual(services.get_profile(self.user), self.profile)

    def test_get_or_create_profile(self):
        self.assertEqual(services.get_or_create_profile(self.user), self.profile)
        fresh = get_user_model().objects.create_user(username="fresh", password=PASSWORD)
        created = services.get_or_create_profile(fresh)
        self.assertEqual((created.owner, created.full_name, created.is_default), (fresh, "fresh", True))

    def test_photo_url_is_empty_when_storage_cannot_build_one(self):
        self.profile.photo = "profile_photos/x.png"
        with mock.patch("django.db.models.fields.files.FieldFile.url", new_callable=mock.PropertyMock) as url:
            url.side_effect = ValueError
            self.assertEqual(services._photo_url(self.profile), "")


class BlankInputTests(_Owner):
    """Spaces only are not a value (Django's required + strip), and inner runs of spaces collapse."""

    def test_whitespace_only_names_are_rejected(self):
        start = "2024-01-01"
        cases = [
            (EducationForm, {"institution": "   ", "start_date": start}, "institution"),
            (ProjectForm, {"project_name": "   "}, "project_name"),
            (SkillForm, {"name": "   ", "proficiency": "beginner"}, "name"),
            (ExperienceForm, {"company": "  ", "job_title": "Dev", "start_date": start}, "company"),
        ]
        for form_class, data, field in cases:
            with self.subTest(form=form_class.__name__):
                kwargs = {} if form_class is ProjectForm else {"profile": self.profile}
                form = form_class(data=data, **kwargs)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
                self.assertEqual(form.errors[field], ["ต้องกรอกช่องนี้"])

    def test_inner_whitespace_is_collapsed(self):
        form = SkillForm(data={"name": "  Machine \t  Learning ", "proficiency": "beginner"}, profile=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["name"], "Machine Learning")

    def test_new_profile_form_keeps_a_label_passed_in(self):
        form = MainProfileForm(instance=MainProfile(owner=self.user), owner=self.user, initial={"label": "สายออกแบบ"})
        self.assertEqual(form["label"].value(), "สายออกแบบ")


class ProfileViewFailureTests(_Owner):
    def test_save_failure_keeps_the_form_and_explains(self):
        url = reverse("profiles:update", args=[self.profile.pk])
        with mock.patch("apps.profiles.services.save_profile", side_effect=DatabaseError):
            response = self.client.post(url, {"label": "Main", "full_name": "Changed"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ระบบขัดข้องชั่วคราว")
        self.assertContains(response, 'value="Changed"')  # input kept
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Owner")

    def test_delete_failure_keeps_the_profile(self):
        with mock.patch("apps.profiles.services.delete_profile", side_effect=DatabaseError):
            response = self.client.post(reverse("profiles:delete", args=[self.profile.pk]))
        self.assertRedirects(response, reverse("profiles:view", args=[self.profile.pk]))
        self.assertIn("ลบโปรไฟล์ไม่สำเร็จ ลองอีกครั้ง", self.messages(response))
        self.assertTrue(MainProfile.objects.filter(pk=self.profile.pk).exists())

    def test_default_profile_shortcuts_open_the_main_profile(self):
        self.assertRedirects(
            self.client.get(reverse("profiles:detail")), reverse("profiles:view", args=[self.profile.pk])
        )
        self.assertRedirects(
            self.client.get(reverse("profiles:edit")), reverse("profiles:update", args=[self.profile.pk])
        )

    def test_default_profile_link_without_a_profile_explains_and_goes_to_create(self):
        fresh = get_user_model().objects.create_user(username="fresh2", password=PASSWORD)
        self.client.force_login(fresh)
        response = self.client.get(reverse("profiles:detail"))
        self.assertRedirects(response, reverse("profiles:create"))
        self.assertEqual(len(self.messages(response)), 1)

    def test_edit_shortcut_without_a_profile_goes_to_create_quietly(self):
        fresh = get_user_model().objects.create_user(username="fresh", password=PASSWORD)
        self.client.force_login(fresh)
        response = self.client.get(reverse("profiles:edit"))
        self.assertRedirects(response, reverse("profiles:create"))
        self.assertEqual(self.messages(response), [])


class SkillRaceTests(_Owner):
    """Two requests can pass the form's duplicate check at once; the database constraint still wins."""

    def setUp(self):
        super().setUp()
        self.skill = Skill.objects.create(profile=self.profile, name="Python")
        self.exp = Experience.objects.create(
            profile=self.profile, company="KU", job_title="TA", start_date=datetime.date(2024, 1, 1)
        )

    def test_create_race_becomes_a_form_error(self):
        with mock.patch("apps.profiles.skills_experience.services.create_skill", side_effect=IntegrityError):
            response = self.client.post(
                reverse("profiles:skill_add", args=[self.profile.pk]), {"name": "Go", "proficiency": "beginner"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "มีทักษะนี้ในโปรไฟล์อยู่แล้ว")

    def test_update_race_becomes_a_form_error(self):
        with mock.patch("apps.profiles.skills_experience.services.update_skill", side_effect=IntegrityError):
            response = self.client.post(
                reverse("profiles:skill_edit", args=[self.skill.pk]), {"name": "Go", "proficiency": "expert"}
            )
        self.assertContains(response, "มีทักษะนี้ในโปรไฟล์อยู่แล้ว")

    def test_invalid_edits_keep_the_user_on_the_form(self):
        skill = self.client.post(reverse("profiles:skill_edit", args=[self.skill.pk]), {"name": "", "proficiency": "x"})
        exp = self.client.post(
            reverse("profiles:experience_edit", args=[self.exp.pk]), {"company": "", "job_title": ""}
        )
        for response in (skill, exp):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "data-error-summary")


class ProfileCardTagTests(_Owner):
    def test_profile_card_renders_the_default_profile(self):
        html = Template("{% load profile_tags %}{% profile_card user %}").render(Context({"user": self.user}))
        self.assertIn("Owner", html)
