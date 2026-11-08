"""Tests for per-version content selection (FOLDO-06, Dev 2)."""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.shortcuts import resolve_url
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.education.models import EducationEntry
from apps.profiles.models import Experience, MainProfile, Project, Skill

from ..models import Portfolio, PortfolioContentSelection, PortfolioContentSetup
from . import selectors, services

PASSWORD = "s3cret-pass"


class SelectionTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", email="a@example.com", password=PASSWORD)
        self.bob = User.objects.create_user(username="bob", email="b@example.com", password=PASSWORD)
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice A")
        self.bob_profile = MainProfile.objects.create(owner=self.bob, full_name="Bob B")
        self.python = Skill.objects.create(profile=self.profile, name="PythonSkillX")
        self.django = Skill.objects.create(profile=self.profile, name="DjangoSkillX")
        self.bob_skill = Skill.objects.create(profile=self.bob_profile, name="BobSecretSkill")
        self.job = Experience.objects.create(
            profile=self.profile, company="AcmeCoX", job_title="InternRoleX", start_date=datetime.date(2024, 6, 1)
        )
        self.project = Project.objects.create(profile=self.profile, project_name="ProjectAlphaX")
        self.school = EducationEntry.objects.create(
            owner=self.alice, level=EducationEntry.Level.UNDERGRADUATE, institution="SchoolUniX"
        )
        self.v1 = Portfolio.objects.create(owner=self.alice, title="Version One", profile=self.profile)
        self.v2 = Portfolio.objects.create(owner=self.alice, title="Version Two", profile=self.profile)
        self.bob_portfolio = Portfolio.objects.create(owner=self.bob, title="Bob Folio", profile=self.bob_profile)
        self.client.force_login(self.alice)

    def url(self, portfolio):
        return reverse("portfolios:content", args=[portfolio.pk])

    def preview(self, portfolio):
        return self.client.get(reverse("portfolios:preview", args=[portfolio.pk])).content.decode()

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def choose(self, portfolio, **sections):
        return self.client.post(self.url(portfolio), sections)


class PrivacyTests(SelectionTestCase):
    def test_owner_sees_page(self):
        self.assertEqual(self.client.get(self.url(self.v1)).status_code, 200)

    def test_other_users_portfolio_is_404(self):
        self.assertEqual(self.client.get(self.url(self.bob_portfolio)).status_code, 404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(self.url(self.v1))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(resolve_url(settings.LOGIN_URL)))

    def test_other_user_cannot_change_selection(self):
        response = self.choose(self.bob_portfolio, skills=[self.bob_skill.pk])
        self.assertEqual(response.status_code, 404)
        self.assertFalse(PortfolioContentSetup.objects.filter(portfolio=self.bob_portfolio).exists())

    def test_visitor_post_changes_nothing(self):
        self.client.logout()
        self.choose(self.v1, skills=[self.python.pk])
        self.assertFalse(PortfolioContentSetup.objects.exists())


class DefaultAndSaveTests(SelectionTestCase):
    def test_never_customised_shows_everything(self):
        self.assertIsNone(selectors.get_selected_ids(self.v1))
        html = self.preview(self.v1)
        for text in ("PythonSkillX", "DjangoSkillX", "InternRoleX", "SchoolUniX"):
            self.assertIn(text, html)

    def test_page_ticks_everything_when_never_customised(self):
        html = self.client.get(self.url(self.v1)).content.decode()
        self.assertEqual(html.count("checked"), 5)  # 2 skills, 1 experience, 1 education, 1 project

    def test_saved_selection_filters_the_preview(self):
        response = self.choose(self.v1, skills=[self.python.pk])
        self.assertRedirects(response, self.url(self.v1))
        html = self.preview(self.v1)
        self.assertIn("PythonSkillX", html)
        for text in ("DjangoSkillX", "InternRoleX", "SchoolUniX"):
            self.assertNotIn(text, html)

    def test_selection_persists_after_logout_and_login(self):
        self.choose(self.v1, skills=[self.django.pk], experience=[self.job.pk])
        self.client.logout()
        self.assertTrue(self.client.login(username="alice", password=PASSWORD))
        self.assertEqual(
            selectors.get_selected_ids(self.v1),
            {"experience": {self.job.pk}, "education": set(), "projects": set(), "skills": {self.django.pk}},
        )

    def test_education_can_be_selected(self):
        self.choose(self.v1, education=[self.school.pk])
        html = self.preview(self.v1)
        self.assertIn("SchoolUniX", html)
        self.assertNotIn("PythonSkillX", html)

    def test_deselecting_everything_shows_nothing_but_keeps_source_data(self):
        self.choose(self.v1)
        html = self.preview(self.v1)
        for text in ("PythonSkillX", "DjangoSkillX", "InternRoleX", "SchoolUniX"):
            self.assertNotIn(text, html)
        self.assertTrue(PortfolioContentSetup.objects.filter(portfolio=self.v1).exists())
        self.assertEqual(Skill.objects.filter(profile=self.profile).count(), 2)
        self.assertTrue(Experience.objects.filter(pk=self.job.pk).exists())
        self.assertTrue(EducationEntry.objects.filter(pk=self.school.pk).exists())

    def test_reset_goes_back_to_everything(self):
        self.choose(self.v1, skills=[self.python.pk])
        self.client.post(self.url(self.v1), {"reset": "1"})
        self.assertIsNone(selectors.get_selected_ids(self.v1))
        self.assertFalse(PortfolioContentSelection.objects.filter(portfolio=self.v1).exists())
        self.assertIn("DjangoSkillX", self.preview(self.v1))


class IndependenceTests(SelectionTestCase):
    def test_changing_one_version_does_not_affect_another(self):
        self.choose(self.v1, skills=[self.python.pk])
        self.choose(self.v2, skills=[self.django.pk], experience=[self.job.pk])
        self.assertEqual(selectors.get_selected_ids(self.v1)["skills"], {self.python.pk})
        self.assertEqual(selectors.get_selected_ids(self.v2)["skills"], {self.django.pk})
        # Changing v2 again leaves v1 exactly as it was.
        self.choose(self.v2)
        self.assertEqual(selectors.get_selected_ids(self.v1)["skills"], {self.python.pk})
        self.assertIn("PythonSkillX", self.preview(self.v1))
        self.assertNotIn("DjangoSkillX", self.preview(self.v1))

    def test_a_customised_version_does_not_change_an_untouched_one(self):
        self.choose(self.v1, skills=[self.python.pk])
        self.assertIsNone(selectors.get_selected_ids(self.v2))
        self.assertIn("DjangoSkillX", self.preview(self.v2))

    def test_deleting_a_version_keeps_profile_data_and_other_versions(self):
        self.choose(self.v1, skills=[self.python.pk])
        self.choose(self.v2, skills=[self.django.pk])
        self.v1.delete()
        self.assertEqual(Skill.objects.filter(profile=self.profile).count(), 2)
        self.assertEqual(selectors.get_selected_ids(self.v2)["skills"], {self.django.pk})


class UnavailableItemTests(SelectionTestCase):
    def test_another_users_ids_are_ignored_with_a_warning(self):
        response = self.choose(self.v1, skills=[self.python.pk, self.bob_skill.pk])
        self.assertTrue(any("no longer available" in m for m in self.messages(response)))
        self.assertEqual(selectors.get_selected_ids(self.v1)["skills"], {self.python.pk})
        self.assertFalse(PortfolioContentSelection.objects.filter(item_id=self.bob_skill.pk, section="skills").exists())

    def test_junk_values_are_ignored(self):
        response = self.choose(self.v1, skills=["abc", "", str(self.python.pk)])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(selectors.get_selected_ids(self.v1)["skills"], {self.python.pk})

    def test_deleted_source_item_is_handled_safely(self):
        self.choose(self.v1, skills=[self.python.pk, self.django.pk])
        self.django.delete()
        self.assertEqual(selectors.get_selected_ids(self.v1)["skills"], {self.python.pk})
        self.assertEqual(self.client.get(self.url(self.v1)).status_code, 200)
        self.assertEqual(self.client.get(reverse("portfolios:preview", args=[self.v1.pk])).status_code, 200)
        # The stale row is cleaned up the next time the selection is saved.
        self.choose(self.v1, skills=[self.python.pk])
        self.assertEqual(PortfolioContentSelection.objects.filter(portfolio=self.v1, section="skills").count(), 1)

    def test_selection_for_a_profile_no_longer_used_is_ignored(self):
        other = MainProfile.objects.create(owner=self.alice, label="Other", full_name="Alice Other")
        self.choose(self.v1, skills=[self.python.pk])
        self.v1.profile = other
        self.v1.save()
        self.assertEqual(selectors.get_selected_ids(self.v1)["skills"], set())

    def test_empty_profile_shows_the_empty_state(self):
        Skill.objects.all().delete()
        Project.objects.all().delete()
        Experience.objects.all().delete()
        EducationEntry.objects.all().delete()
        html = self.client.get(self.url(self.v1)).content.decode()
        self.assertIn("Nothing to choose from yet", html)


class ServiceTests(SelectionTestCase):
    def test_save_selection_returns_ignored_count(self):
        self.assertEqual(services.save_selection(self.v1, {"skills": [self.python.pk, 99999]}), 1)

    def test_save_selection_twice_is_stable(self):
        services.save_selection(self.v1, {"skills": [self.python.pk]})
        services.save_selection(self.v1, {"skills": [self.python.pk]})
        self.assertEqual(PortfolioContentSelection.objects.filter(portfolio=self.v1).count(), 1)
        self.assertEqual(PortfolioContentSetup.objects.filter(portfolio=self.v1).count(), 1)

    def test_selection_matches_the_rendering_contract(self):
        """The mapping can be passed straight to apps.rendering's build_portfolio_content(selected=...)."""
        from apps.rendering.selectors import build_portfolio_content

        services.save_selection(self.v1, {"skills": [self.python.pk]})
        content = build_portfolio_content(self.profile, selected=selectors.get_selected_ids(self.v1))
        skills = content.section("skills")
        self.assertEqual([item.title for item in skills.items], ["PythonSkillX"])
        self.assertIsNone(content.section("experience"))


class ProjectSelectionTests(SelectionTestCase):
    def test_projects_are_shown_by_default(self):
        self.assertIn("ProjectAlphaX", self.preview(self.v1))

    def test_project_can_be_deselected_without_deleting_it(self):
        self.choose(self.v1, skills=[self.python.pk])
        self.assertNotIn("ProjectAlphaX", self.preview(self.v1))
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_project_can_be_selected_in_one_version_only(self):
        self.choose(self.v1, projects=[self.project.pk])
        self.choose(self.v2, skills=[self.python.pk])
        self.assertIn("ProjectAlphaX", self.preview(self.v1))
        self.assertNotIn("ProjectAlphaX", self.preview(self.v2))
