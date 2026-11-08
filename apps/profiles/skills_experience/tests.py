"""Tests for skills and experience (FOLDO-04, Dev 2)."""

import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.shortcuts import resolve_url
from django.urls import reverse

from ..models import Experience, MainProfile, Skill
from . import services
from .forms import ExperienceForm, SkillForm

PASSWORD = "s3cret-pass"


class SkillsExperienceTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", email="alice@example.com", password=PASSWORD)
        self.bob = User.objects.create_user(username="bob", email="bob@example.com", password=PASSWORD)
        self.alice_profile = MainProfile.objects.create(owner=self.alice, full_name="Alice A")
        self.bob_profile = MainProfile.objects.create(owner=self.bob, full_name="Bob B")
        self.alice_skill = Skill.objects.create(profile=self.alice_profile, name="Python")
        self.bob_skill = Skill.objects.create(profile=self.bob_profile, name="Secret Skill")
        self.alice_exp = self._experience(self.alice_profile, "Acme", "Intern")
        self.bob_exp = self._experience(self.bob_profile, "Hidden Co", "Spy")
        self.client.force_login(self.alice)

    def _experience(self, profile, company, title, start=datetime.date(2024, 6, 1), end=None):
        return Experience.objects.create(
            profile=profile, company=company, job_title=title, start_date=start, end_date=end
        )

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class PrivacyTests(SkillsExperienceTestCase):
    """Every private page: owner 200, other user 404, visitor redirected to login."""

    def pages(self):
        return {
            "overview": reverse("profiles:skills_experience", args=[self.alice_profile.pk]),
            "skill add": reverse("profiles:skill_add", args=[self.alice_profile.pk]),
            "skill edit": reverse("profiles:skill_edit", args=[self.alice_skill.pk]),
            "skill delete": reverse("profiles:skill_delete", args=[self.alice_skill.pk]),
            "experience add": reverse("profiles:experience_add", args=[self.alice_profile.pk]),
            "experience edit": reverse("profiles:experience_edit", args=[self.alice_exp.pk]),
            "experience delete": reverse("profiles:experience_delete", args=[self.alice_exp.pk]),
        }

    def test_owner_can_open_every_page(self):
        for name, url in self.pages().items():
            with self.subTest(page=name):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_other_user_gets_404_on_every_page(self):
        self.client.force_login(self.bob)
        for name, url in self.pages().items():
            with self.subTest(page=name):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_visitor_is_sent_to_login_on_every_page(self):
        self.client.logout()
        for name, url in self.pages().items():
            with self.subTest(page=name):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(resolve_url(settings.LOGIN_URL)))

    def test_other_user_cannot_change_anything_by_post(self):
        self.client.force_login(self.bob)
        pages = self.pages()
        self.client.post(pages["skill add"], {"name": "Injected", "proficiency": "expert"})
        self.client.post(pages["skill edit"], {"name": "Hacked", "proficiency": "expert"})
        self.client.post(pages["skill delete"])
        self.client.post(
            pages["experience add"],
            {"company": "X", "job_title": "Y", "start_date": "2024-01-01"},
        )
        self.client.post(
            pages["experience edit"],
            {"company": "Hacked", "job_title": "Hacked", "start_date": "2024-01-01"},
        )
        self.client.post(pages["experience delete"])

        self.assertEqual(list(self.alice_profile.skills.values_list("name", flat=True)), ["Python"])
        self.assertEqual(self.alice_profile.experiences.count(), 1)
        self.alice_exp.refresh_from_db()
        self.assertEqual(self.alice_exp.company, "Acme")

    def test_overview_never_shows_another_users_data(self):
        response = self.client.get(self.pages()["overview"])
        for leaked in ("Secret Skill", "Hidden Co", "Spy"):
            self.assertNotContains(response, leaked)


class SkillTests(SkillsExperienceTestCase):
    def test_add_skill_persists_and_redirects_with_message(self):
        url = reverse("profiles:skill_add", args=[self.alice_profile.pk])
        response = self.client.post(url, {"name": "  Django  ", "proficiency": "advanced"})
        self.assertRedirects(response, reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        skill = self.alice_profile.skills.get(name="Django")
        self.assertEqual(skill.proficiency, "advanced")
        self.assertEqual(self.messages(response), ["Skill “Django” added."])

    def test_profile_in_post_data_is_ignored(self):
        url = reverse("profiles:skill_add", args=[self.alice_profile.pk])
        self.client.post(url, {"name": "Sneaky", "proficiency": "beginner", "profile": self.bob_profile.pk})
        self.assertTrue(self.alice_profile.skills.filter(name="Sneaky").exists())
        self.assertFalse(self.bob_profile.skills.filter(name="Sneaky").exists())

    def test_duplicate_name_is_rejected_ignoring_case_and_spaces(self):
        url = reverse("profiles:skill_add", args=[self.alice_profile.pk])
        response = self.client.post(url, {"name": "  pYTHON ", "proficiency": "beginner"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        self.assertEqual(self.alice_profile.skills.count(), 1)

    def test_same_name_is_allowed_for_other_profile_or_user(self):
        second = MainProfile.objects.create(owner=self.alice, label="Second", full_name="Alice A")
        self.assertTrue(SkillForm({"name": "Python", "proficiency": "beginner"}, profile=second).is_valid())
        self.assertTrue(
            SkillForm({"name": "Secret Skill", "proficiency": "beginner"}, profile=self.alice_profile).is_valid()
        )

    def test_invalid_input_is_rejected(self):
        bad = [
            {"name": "", "proficiency": "beginner"},
            {"name": "   ", "proficiency": "beginner"},
            {"name": "x" * 101, "proficiency": "beginner"},
            {"name": "Go", "proficiency": "wizard"},
        ]
        for data in bad:
            with self.subTest(data=data):
                self.assertFalse(SkillForm(data, profile=self.alice_profile).is_valid())

    def test_database_blocks_duplicate_skill_names(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Skill.objects.create(profile=self.alice_profile, name="PYTHON")

    def test_edit_skill(self):
        url = reverse("profiles:skill_edit", args=[self.alice_skill.pk])
        response = self.client.post(url, {"name": "Python 3", "proficiency": "expert"})
        self.assertRedirects(response, reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        self.alice_skill.refresh_from_db()
        self.assertEqual((self.alice_skill.name, self.alice_skill.proficiency), ("Python 3", "expert"))

    def test_edit_can_keep_its_own_name(self):
        form = SkillForm(
            {"name": "Python", "proficiency": "expert"}, instance=self.alice_skill, profile=self.alice_profile
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_delete_asks_first_then_deletes_on_post(self):
        url = reverse("profiles:skill_delete", args=[self.alice_skill.pk])
        self.assertContains(self.client.get(url), "Python")
        self.assertTrue(Skill.objects.filter(pk=self.alice_skill.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        self.assertFalse(Skill.objects.filter(pk=self.alice_skill.pk).exists())
        self.assertEqual(self.messages(response), ["Skill “Python” deleted."])


class ExperienceTests(SkillsExperienceTestCase):
    def valid_data(self, **overrides):
        data = {
            "company": "  Globex  ",
            "job_title": "Backend Intern",
            "start_date": "2025-06-01",
            "end_date": "2025-08-31",
            "description": "  Built APIs.  ",
        }
        data.update(overrides)
        return data

    def test_add_experience_persists_and_cleans_text(self):
        url = reverse("profiles:experience_add", args=[self.alice_profile.pk])
        response = self.client.post(url, self.valid_data())
        self.assertRedirects(response, reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        exp = self.alice_profile.experiences.get(job_title="Backend Intern")
        self.assertEqual((exp.company, exp.description), ("Globex", "Built APIs."))
        self.assertEqual(exp.end_date, datetime.date(2025, 8, 31))
        self.assertEqual(self.messages(response), ["Experience “Backend Intern” added."])

    def test_empty_end_date_means_current(self):
        url = reverse("profiles:experience_add", args=[self.alice_profile.pk])
        self.client.post(url, self.valid_data(end_date="", job_title="Current job"))
        exp = self.alice_profile.experiences.get(job_title="Current job")
        self.assertIsNone(exp.end_date)
        self.assertTrue(exp.is_current)

    def test_end_before_start_is_rejected(self):
        url = reverse("profiles:experience_add", args=[self.alice_profile.pk])
        response = self.client.post(url, self.valid_data(start_date="2025-09-01", end_date="2025-01-01"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("end_date", response.context["form"].errors)
        self.assertEqual(self.alice_profile.experiences.count(), 1)

    def test_invalid_input_is_rejected(self):
        bad = [
            self.valid_data(company=""),
            self.valid_data(company="   "),
            self.valid_data(job_title=""),
            self.valid_data(company="x" * 201),
            self.valid_data(description="x" * 5001),
            self.valid_data(start_date=""),
            self.valid_data(start_date="not-a-date"),
        ]
        for data in bad:
            with self.subTest(data=data):
                self.assertFalse(ExperienceForm(data, profile=self.alice_profile).is_valid())

    def test_database_blocks_end_before_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._experience(
                self.alice_profile, "Bad", "Bad", start=datetime.date(2025, 5, 1), end=datetime.date(2025, 1, 1)
            )

    def test_edit_experience(self):
        url = reverse("profiles:experience_edit", args=[self.alice_exp.pk])
        response = self.client.post(url, self.valid_data(job_title="Junior Dev"))
        self.assertRedirects(response, reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        self.alice_exp.refresh_from_db()
        self.assertEqual(self.alice_exp.job_title, "Junior Dev")
        self.assertEqual(self.alice_exp.company, "Globex")

    def test_delete_asks_first_then_deletes_on_post(self):
        url = reverse("profiles:experience_delete", args=[self.alice_exp.pk])
        self.assertContains(self.client.get(url), "Intern")
        self.assertTrue(Experience.objects.filter(pk=self.alice_exp.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        self.assertFalse(Experience.objects.filter(pk=self.alice_exp.pk).exists())

    def test_overview_lists_newest_first_and_shows_present(self):
        self._experience(self.alice_profile, "Newer Co", "Dev", start=datetime.date(2025, 9, 1))
        response = self.client.get(reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        companies = [e.company for e in response.context["experiences"]]
        self.assertEqual(companies, ["Newer Co", "Acme"])
        self.assertContains(response, "Present")


class EmptyStateAndPersistenceTests(SkillsExperienceTestCase):
    def test_empty_profile_shows_empty_states_with_add_links(self):
        empty = MainProfile.objects.create(owner=self.alice, label="Empty", full_name="Alice A")
        response = self.client.get(reverse("profiles:skills_experience", args=[empty.pk]))
        self.assertContains(response, "No skills yet")
        self.assertContains(response, "No experience yet")
        self.assertContains(response, reverse("profiles:skill_add", args=[empty.pk]))
        self.assertContains(response, reverse("profiles:experience_add", args=[empty.pk]))

    def test_filled_profile_has_no_empty_state(self):
        response = self.client.get(reverse("profiles:skills_experience", args=[self.alice_profile.pk]))
        self.assertNotContains(response, "No skills yet")
        self.assertNotContains(response, "No experience yet")

    def test_changes_survive_refresh_and_a_new_login(self):
        add_skill = reverse("profiles:skill_add", args=[self.alice_profile.pk])
        add_exp = reverse("profiles:experience_add", args=[self.alice_profile.pk])
        self.client.post(add_skill, {"name": "Docker", "proficiency": "intermediate"})
        self.client.post(
            add_exp, {"company": "Initech", "job_title": "Analyst", "start_date": "2024-01-01"}
        )
        overview = reverse("profiles:skills_experience", args=[self.alice_profile.pk])
        self.assertContains(self.client.get(overview), "Docker")  # refresh

        self.client.logout()
        self.assertTrue(self.client.login(username="alice", password=PASSWORD))
        response = self.client.get(overview)
        self.assertContains(response, "Docker")
        self.assertContains(response, "Analyst")

    def test_profile_page_links_to_skills_and_experience(self):
        response = self.client.get(reverse("profiles:view", args=[self.alice_profile.pk]))
        self.assertContains(response, reverse("profiles:skills_experience", args=[self.alice_profile.pk]))

    def test_deleting_a_profile_removes_its_skills_and_experience(self):
        self.alice_profile.delete()
        self.assertFalse(Skill.objects.filter(pk=self.alice_skill.pk).exists())
        self.assertFalse(Experience.objects.filter(pk=self.alice_exp.pk).exists())
        self.assertTrue(Skill.objects.filter(pk=self.bob_skill.pk).exists())


class ServiceTests(SkillsExperienceTestCase):
    def test_create_and_update_use_only_known_fields(self):
        skill = services.create_skill(
            profile=self.alice_profile, data={"name": "Git", "proficiency": "beginner", "profile": self.bob_profile}
        )
        self.assertEqual(skill.profile, self.alice_profile)
        services.update_skill(skill=skill, data={"name": "Git", "proficiency": "expert", "id": 999})
        skill.refresh_from_db()
        self.assertEqual(skill.proficiency, "expert")
        self.assertNotEqual(skill.pk, 999)

    def test_delete_services(self):
        services.delete_skill(skill=self.alice_skill)
        services.delete_experience(experience=self.alice_exp)
        self.assertEqual(self.alice_profile.skills.count(), 0)
        self.assertEqual(self.alice_profile.experiences.count(), 0)
