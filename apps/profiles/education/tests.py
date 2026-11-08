"""Tests for education on a Main Profile (FOLDO-04, Dev 1)."""

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import DatabaseError, IntegrityError
from django.test import TestCase
from django.urls import reverse

from apps.core.validators import MAX_LONG_TEXT, MAX_SHORT_TEXT

from ..models import Education, MainProfile
from .forms import MAX_YEARS_AHEAD, EducationForm

PASSWORD = "pw-Foldo-12345"


def make_user(username):
    return get_user_model().objects.create_user(username=username, password=PASSWORD)


def make_profile(owner, label="Main profile"):
    return MainProfile.objects.create(owner=owner, label=label, full_name=owner.username.title())


def make_education(profile, **fields):
    fields.setdefault("institution", "Thammasat University")
    fields.setdefault("start_date", datetime.date(2022, 8, 1))
    return Education.objects.create(profile=profile, **fields)


def form_data(**overrides):
    data = {
        "institution": "Thammasat University",
        "degree": "B.Eng.",
        "field_of_study": "Computer Engineering",
        "start_date": "2022-08-01",
        "end_date": "2026-05-31",
        "grade": "3.50",
        "description": "Robotics club.",
    }
    data.update(overrides)
    return data


class EducationTestCase(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.profile = make_profile(self.alice)
        self.bob_profile = make_profile(self.bob)
        self.client.force_login(self.alice)

    def levels(self, response):
        return [m.level_tag for m in get_messages(response.wsgi_request)]


class AccessControlTests(EducationTestCase):
    """Owner → 200, another user → 404, not signed in → login (docs/CONVENTIONS.md §6)."""

    def setUp(self):
        super().setUp()
        self.own = make_education(self.profile)
        self.others = make_education(self.bob_profile, institution="Bob's school")

    def urls_for(self, profile, education):
        return [
            reverse("profiles:education_list", args=[profile.pk]),
            reverse("profiles:education_add", args=[profile.pk]),
            reverse("profiles:education_edit", args=[education.pk]),
            reverse("profiles:education_delete", args=[education.pk]),
        ]

    def test_owner_gets_200(self):
        for url in self.urls_for(self.profile, self.own):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_other_user_gets_404(self):
        for url in self.urls_for(self.bob_profile, self.others):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        login = reverse("accounts:login")
        for url in self.urls_for(self.profile, self.own):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(login))

    def test_unknown_ids_get_404(self):
        self.assertEqual(self.client.get(reverse("profiles:education_list", args=[99999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("profiles:education_edit", args=[99999])).status_code, 404)

    def test_cannot_add_to_someone_elses_profile(self):
        response = self.client.post(reverse("profiles:education_add", args=[self.bob_profile.pk]), form_data())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.bob_profile.educations.count(), 1)

    def test_cannot_edit_someone_elses_entry(self):
        url = reverse("profiles:education_edit", args=[self.others.pk])
        response = self.client.post(url, form_data(institution="Hacked"))
        self.assertEqual(response.status_code, 404)
        self.others.refresh_from_db()
        self.assertEqual(self.others.institution, "Bob's school")

    def test_cannot_delete_someone_elses_entry(self):
        response = self.client.post(reverse("profiles:education_delete", args=[self.others.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Education.objects.filter(pk=self.others.pk).exists())

    def test_list_shows_only_this_profiles_entries(self):
        second = make_profile(self.alice, label="Design")
        make_education(second, institution="Design school")
        response = self.client.get(reverse("profiles:education_list", args=[self.profile.pk]))
        self.assertContains(response, "Thammasat University")
        self.assertNotContains(response, "Design school")
        self.assertNotContains(response, "Bob&#x27;s school")

    def test_profile_field_in_post_is_ignored(self):
        """The owning profile comes from the URL looked up via request.user, never from the form."""
        url = reverse("profiles:education_add", args=[self.profile.pk])
        self.client.post(url, form_data(institution="Sneaky", profile=self.bob_profile.pk))
        self.assertTrue(self.profile.educations.filter(institution="Sneaky").exists())
        self.assertFalse(self.bob_profile.educations.filter(institution="Sneaky").exists())


class CrudTests(EducationTestCase):
    def test_empty_state(self):
        response = self.client.get(reverse("profiles:education_list", args=[self.profile.pk]))
        self.assertContains(response, "ยังไม่มีข้อมูลการศึกษา")
        self.assertContains(response, reverse("profiles:education_add", args=[self.profile.pk]))

    def test_create_with_all_fields(self):
        response = self.client.post(reverse("profiles:education_add", args=[self.profile.pk]), form_data())
        self.assertRedirects(response, reverse("profiles:education_list", args=[self.profile.pk]))
        education = self.profile.educations.get()
        self.assertEqual(education.degree, "B.Eng.")
        self.assertEqual(education.end_date, datetime.date(2026, 5, 31))
        self.assertIn("success", self.levels(response))

    def test_create_with_only_required_fields(self):
        data = {"institution": "Triam Udom", "start_date": "2016-05-16"}
        response = self.client.post(reverse("profiles:education_add", args=[self.profile.pk]), data)
        self.assertEqual(response.status_code, 302)
        education = self.profile.educations.get()
        self.assertTrue(education.is_current)
        self.assertEqual(education.degree, "")

    def test_edit(self):
        education = make_education(self.profile)
        url = reverse("profiles:education_edit", args=[education.pk])
        self.assertContains(self.client.get(url), 'value="Thammasat University"')
        response = self.client.post(url, form_data(degree="M.Eng.", end_date=""))
        self.assertRedirects(response, reverse("profiles:education_list", args=[self.profile.pk]))
        education.refresh_from_db()
        self.assertEqual(education.degree, "M.Eng.")
        self.assertIsNone(education.end_date)

    def test_delete_asks_first_then_removes(self):
        education = make_education(self.profile)
        url = reverse("profiles:education_delete", args=[education.pk])
        self.assertContains(self.client.get(url), "ยืนยันลบ")
        self.assertTrue(Education.objects.filter(pk=education.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse("profiles:education_list", args=[self.profile.pk]))
        self.assertFalse(Education.objects.filter(pk=education.pk).exists())

    def test_list_shows_present_for_current_studies(self):
        make_education(self.profile, institution="Current uni")
        response = self.client.get(reverse("profiles:education_list", args=[self.profile.pk]))
        self.assertContains(response, "ปัจจุบัน")

    def test_ordering_current_first_then_latest(self):
        old = make_education(self.profile, institution="Old", start_date=datetime.date(2010, 1, 1),
                             end_date=datetime.date(2013, 1, 1))
        recent = make_education(self.profile, institution="Recent", start_date=datetime.date(2014, 1, 1),
                                end_date=datetime.date(2018, 1, 1))
        current = make_education(self.profile, institution="Current", start_date=datetime.date(2020, 1, 1))
        self.assertEqual(list(self.profile.educations.all()), [current, recent, old])

    def test_user_text_is_escaped(self):
        make_education(self.profile, institution="<script>alert(1)</script>")
        response = self.client.get(reverse("profiles:education_list", args=[self.profile.pk]))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_profile_detail_links_to_education(self):
        response = self.client.get(reverse("profiles:view", args=[self.profile.pk]))
        self.assertContains(response, reverse("profiles:education_list", args=[self.profile.pk]))

    def test_deleting_profile_deletes_its_education(self):
        make_education(self.profile)
        self.profile.delete()
        self.assertFalse(Education.objects.filter(profile_id=self.profile.pk).exists())


class PersistenceTests(EducationTestCase):
    def test_entry_survives_logout_and_login(self):
        self.client.post(reverse("profiles:education_add", args=[self.profile.pk]), form_data())
        self.client.logout()
        self.assertTrue(self.client.login(username="alice", password=PASSWORD))
        response = self.client.get(reverse("profiles:education_list", args=[self.profile.pk]))
        self.assertContains(response, "Thammasat University")
        self.assertContains(response, "Computer Engineering")


class ValidationTests(EducationTestCase):
    def form(self, **overrides):
        return EducationForm(data=form_data(**overrides), profile=self.profile)

    def test_valid(self):
        self.assertTrue(self.form().is_valid())

    def test_institution_required_and_whitespace_only_rejected(self):
        for value in ("", "   "):
            with self.subTest(value=repr(value)):
                form = self.form(institution=value)
                self.assertFalse(form.is_valid())
                self.assertIn("institution", form.errors)

    def test_text_is_trimmed_and_collapsed(self):
        form = self.form(institution="  Thammasat   University ", degree=" B.Eng. ", grade=" 3.5 ")
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["institution"], "Thammasat University")
        self.assertEqual(form.cleaned_data["degree"], "B.Eng.")
        self.assertEqual(form.cleaned_data["grade"], "3.5")

    def test_max_lengths(self):
        self.assertFalse(self.form(institution="x" * (MAX_SHORT_TEXT + 1)).is_valid())
        self.assertFalse(self.form(degree="x" * (MAX_SHORT_TEXT + 1)).is_valid())
        self.assertFalse(self.form(grade="x" * 51).is_valid())
        self.assertFalse(self.form(description="x" * (MAX_LONG_TEXT + 1)).is_valid())

    def test_start_date_required_and_must_be_a_date(self):
        self.assertIn("start_date", self.form(start_date="").errors)
        self.assertIn("start_date", self.form(start_date="not-a-date").errors)

    def test_end_before_start_rejected(self):
        form = self.form(start_date="2022-08-01", end_date="2022-07-31")
        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_same_start_and_end_allowed(self):
        self.assertTrue(self.form(start_date="2022-08-01", end_date="2022-08-01").is_valid())

    def test_start_in_future_rejected(self):
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        self.assertIn("start_date", self.form(start_date=tomorrow.isoformat(), end_date="").errors)

    def test_start_before_1900_rejected(self):
        self.assertIn("start_date", self.form(start_date="1899-12-31").errors)

    def test_expected_graduation_in_future_allowed_within_limit(self):
        today = datetime.date.today()
        ok = datetime.date(today.year + MAX_YEARS_AHEAD, 1, 1)
        too_far = datetime.date(today.year + MAX_YEARS_AHEAD + 1, 1, 1)
        self.assertTrue(self.form(end_date=ok.isoformat()).is_valid())
        self.assertIn("end_date", self.form(end_date=too_far.isoformat()).errors)

    def test_database_rejects_end_before_start(self):
        with self.assertRaises(IntegrityError):
            make_education(self.profile, start_date=datetime.date(2022, 1, 1), end_date=datetime.date(2021, 1, 1))

    def test_invalid_post_keeps_input_and_shows_error(self):
        url = reverse("profiles:education_add", args=[self.profile.pk])
        response = self.client.post(url, form_data(start_date="2022-08-01", end_date="2020-01-01"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "End date can&#x27;t be before the start date.")
        self.assertContains(response, 'value="Computer Engineering"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertIn("danger", self.levels(response))
        self.assertFalse(self.profile.educations.exists())


class ErrorStateTests(EducationTestCase):
    def test_database_error_on_save_keeps_form(self):
        url = reverse("profiles:education_add", args=[self.profile.pk])
        with mock.patch("apps.profiles.education.services.create_education", side_effect=DatabaseError):
            with self.assertLogs("apps.profiles.education.views", level="ERROR"):
                response = self.client.post(url, form_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temporary problem")
        self.assertContains(response, 'value="Thammasat University"')
        self.assertIn("danger", self.levels(response))

    def test_database_error_on_delete_keeps_entry(self):
        education = make_education(self.profile)
        url = reverse("profiles:education_delete", args=[education.pk])
        with mock.patch("apps.profiles.education.services.delete_education", side_effect=DatabaseError):
            with self.assertLogs("apps.profiles.education.views", level="ERROR"):
                response = self.client.post(url)
        self.assertRedirects(response, reverse("profiles:education_list", args=[self.profile.pk]))
        self.assertIn("danger", self.levels(response))
        self.assertTrue(Education.objects.filter(pk=education.pk).exists())
