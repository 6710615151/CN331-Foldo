"""Tests for projects and Project Story (FOLDO-04, FOLDO-15)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse
from ..models import MainProfile, Project
from .forms import ProjectForm


class ProjectTestCase(TestCase):
    """Two users, each with one profile, ready for project tests."""

    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="s3cret-pass")
        self.bobby = User.objects.create_user(username="bobby", password="s3cret-pass")
        self.alice_profile = MainProfile.objects.create(owner=self.alice, full_name="Alice")
        self.bobby_profile = MainProfile.objects.create(owner=self.bobby, full_name="Bobby")

    def make_project(self, profile=None, **fields):
        fields.setdefault("project_name", "FOLDO")
        return Project.objects.create(profile=profile or self.alice_profile, **fields)


class ProjectModelTests(ProjectTestCase):
    def test_project_needs_only_a_name(self):
        project = self.make_project()
        project.full_clean()  # must not raise
        self.assertEqual(str(project), "FOLDO")

    def test_old_project_without_story_still_works(self):
        """Projects made before FOLDO-15 have every story part blank."""
        project = self.make_project()
        project.refresh_from_db()
        self.assertFalse(project.has_story)
        for name in Project.STORY_FIELDS:
            self.assertEqual(getattr(project, name), "")

    def test_story_is_saved_with_the_project(self):
        project = self.make_project(problem="Slow sign-up", outcome="2x more sign-ups")
        project.refresh_from_db()
        self.assertTrue(project.has_story)
        self.assertEqual(project.problem, "Slow sign-up")
        self.assertEqual(project.outcome, "2x more sign-ups")

    def test_end_date_before_start_date_is_rejected(self):
        project = Project(
            profile=self.alice_profile, project_name="FOLDO",
            start_date=date(2026, 5, 1), end_date=date(2026, 4, 30),
        )
        with self.assertRaises(ValidationError) as caught:
            project.full_clean()
        self.assertIn("end_date", caught.exception.message_dict)

    def test_database_also_blocks_end_before_start(self):
        """Even code that skips full_clean() cannot save bad dates."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_project(start_date=date(2026, 5, 1), end_date=date(2026, 4, 30))

    def test_project_url_must_be_http_or_https(self):
        project = Project(profile=self.alice_profile, project_name="FOLDO", project_url="ftp://example.com")
        with self.assertRaises(ValidationError) as caught:
            project.full_clean()
        self.assertIn("project_url", caught.exception.message_dict)

    def test_newest_projects_come_first_and_undated_last(self):
        old = self.make_project(project_name="Old", start_date=date(2024, 1, 1))
        undated = self.make_project(project_name="Undated")
        new = self.make_project(project_name="New", start_date=date(2026, 1, 1))
        self.assertEqual(list(self.alice_profile.projects.all()), [new, old, undated])

    def test_deleting_a_profile_deletes_its_projects(self):
        self.make_project()
        self.alice_profile.delete()
        self.assertFalse(Project.objects.exists())


class ProjectOwnershipTests(ProjectTestCase):
    def test_owner_path_finds_only_the_users_own_projects(self):
        """owner_field "profile__owner" (docs/CONVENTIONS.md) keeps data private."""
        mine = self.make_project(profile=self.alice_profile)
        self.make_project(profile=self.bobby_profile)
        self.assertEqual(list(Project.objects.filter(profile__owner=self.alice.pk)), [mine])


class ProjectStoryPartialTests(ProjectTestCase):
    """templates/partials/project_story.html works with a real Project."""

    def _render(self, project):
        template = Template('{% include "partials/project_story.html" with project=project %}')
        return template.render(Context({"project": project}))

    def test_real_project_story_is_shown(self):
        html = self._render(self.make_project(problem="Slow sign-up"))
        self.assertIn("Slow sign-up", html)

    def test_real_project_without_story_shows_nothing(self):
        self.assertNotIn("<section", self._render(self.make_project()))


class ProjectFormTests(ProjectTestCase):
    def test_name_alone_is_enough(self):
        form = ProjectForm(data={"project_name": "FOLDO"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_blank_or_spaces_only_name_is_rejected(self):
        form = ProjectForm(data={"project_name": "   "})
        self.assertFalse(form.is_valid())
        self.assertIn("project_name", form.errors)

    def test_end_date_before_start_date_shows_under_end_date(self):
        form = ProjectForm(data={"project_name": "FOLDO", "start_date": "2026-05-01", "end_date": "2026-04-30"})
        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_link_without_scheme_becomes_https(self):
        form = ProjectForm(data={"project_name": "FOLDO", "project_url": "github.com/me/foldo"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["project_url"], "https://github.com/me/foldo")

    def test_non_web_link_is_rejected(self):
        form = ProjectForm(data={"project_name": "FOLDO", "project_url": "ftp://example.com/cv.pdf"})
        self.assertFalse(form.is_valid())
        self.assertIn("project_url", form.errors)

    def test_story_parts_are_saved(self):
        form = ProjectForm(data={"project_name": "FOLDO", "problem": "Slow sign-up", "outcome": "2x"})
        self.assertTrue(form.is_valid(), form.errors)
        project = form.save(commit=False)
        project.profile = self.alice_profile
        project.save()
        project.refresh_from_db()
        self.assertEqual((project.problem, project.outcome), ("Slow sign-up", "2x"))

    def test_profile_cannot_be_chosen_in_the_form(self):
        """The profile comes from the URL + signed-in user, never from posted data."""
        self.assertNotIn("profile", ProjectForm().fields)

    def test_fields_use_the_shared_bootstrap_look(self):
        html = str(ProjectForm()["project_name"])
        self.assertIn("form-control", html)


class ProjectPagesTests(ProjectTestCase):
    """The pages: list / add / detail / edit / delete, and who may open them."""

    def setUp(self):
        super().setUp()
        self.project = self.make_project(project_name="FOLDO", problem="Slow sign-up")
        self.client.force_login(self.alice)

    def urls_for(self, project, profile):
        return {
            "list": reverse("profiles:projects", args=[profile.pk]),
            "add": reverse("profiles:project_add", args=[profile.pk]),
            "detail": reverse("profiles:project_detail", args=[project.pk]),
            "edit": reverse("profiles:project_edit", args=[project.pk]),
            "delete": reverse("profiles:project_delete", args=[project.pk]),
        }

    # --- the 3 privacy tests (docs/CONVENTIONS.md section 6) -----------------

    def test_owner_can_open_every_page(self):
        for name, url in self.urls_for(self.project, self.alice_profile).items():
            with self.subTest(page=name):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_other_user_gets_404_on_every_page(self):
        self.client.force_login(self.bobby)
        for name, url in self.urls_for(self.project, self.alice_profile).items():
            with self.subTest(page=name):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_not_signed_in_is_sent_to_login(self):
        self.client.logout()
        for name, url in self.urls_for(self.project, self.alice_profile).items():
            with self.subTest(page=name):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response.url)

    # --- list ---------------------------------------------------------------

    def test_list_shows_only_this_profiles_projects(self):
        self.make_project(profile=self.bobby_profile, project_name="Bobby's secret")
        response = self.client.get(reverse("profiles:projects", args=[self.alice_profile.pk]))
        self.assertContains(response, "FOLDO")
        self.assertNotContains(response, "Bobby&#x27;s secret")
        self.assertNotContains(response, "Bobby's secret")

    def test_empty_list_shows_the_empty_state(self):
        self.project.delete()
        response = self.client.get(reverse("profiles:projects", args=[self.alice_profile.pk]))
        self.assertContains(response, "ยังไม่มีโปรเจกต์")
        self.assertContains(response, reverse("profiles:project_add", args=[self.alice_profile.pk]))

    # --- add ----------------------------------------------------------------

    def test_add_saves_the_project_on_this_profile(self):
        response = self.client.post(
            reverse("profiles:project_add", args=[self.alice_profile.pk]),
            {"project_name": "Portfolio site", "outcome": "Got an internship"},
        )
        project = Project.objects.get(project_name="Portfolio site")
        self.assertEqual(project.profile, self.alice_profile)
        self.assertRedirects(response, reverse("profiles:project_detail", args=[project.pk]))

    def test_add_ignores_a_posted_profile(self):
        """Mass assignment: sending someone else's profile id must not move the project."""
        self.client.post(
            reverse("profiles:project_add", args=[self.alice_profile.pk]),
            {"project_name": "Sneaky", "profile": self.bobby_profile.pk},
        )
        self.assertEqual(Project.objects.get(project_name="Sneaky").profile, self.alice_profile)

    def test_cannot_add_to_someone_elses_profile(self):
        response = self.client.post(
            reverse("profiles:project_add", args=[self.bobby_profile.pk]), {"project_name": "Sneaky"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Project.objects.filter(project_name="Sneaky").exists())

    def test_invalid_add_shows_errors_and_saves_nothing(self):
        response = self.client.post(
            reverse("profiles:project_add", args=[self.alice_profile.pk]),
            {"project_name": "Bad dates", "start_date": "2026-05-01", "end_date": "2026-04-30"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "is-invalid")
        self.assertFalse(Project.objects.filter(project_name="Bad dates").exists())

    # --- detail -------------------------------------------------------------

    def test_detail_shows_the_story(self):
        response = self.client.get(reverse("profiles:project_detail", args=[self.project.pk]))
        self.assertContains(response, "Slow sign-up")

    def test_detail_of_old_project_without_story_still_works(self):
        old = self.make_project(project_name="Old project")
        response = self.client.get(reverse("profiles:project_detail", args=[old.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "foldo-story")

    # --- edit / delete ------------------------------------------------------

    def test_edit_changes_the_project(self):
        self.client.post(
            reverse("profiles:project_edit", args=[self.project.pk]),
            {"project_name": "FOLDO v2", "role": "Dev 4"},
        )
        self.project.refresh_from_db()
        self.assertEqual((self.project.project_name, self.project.role), ("FOLDO v2", "Dev 4"))

    def test_other_user_cannot_edit(self):
        self.client.force_login(self.bobby)
        response = self.client.post(
            reverse("profiles:project_edit", args=[self.project.pk]), {"project_name": "Hacked"}
        )
        self.assertEqual(response.status_code, 404)
        self.project.refresh_from_db()
        self.assertEqual(self.project.project_name, "FOLDO")

    def test_delete_removes_the_project(self):
        response = self.client.post(reverse("profiles:project_delete", args=[self.project.pk]))
        self.assertRedirects(response, reverse("profiles:projects", args=[self.alice_profile.pk]))
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_other_user_cannot_delete(self):
        self.client.force_login(self.bobby)
        response = self.client.post(reverse("profiles:project_delete", args=[self.project.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_saved_project_is_still_there_after_signing_in_again(self):
        """Sprint 2: changes persist after refresh and login."""
        self.client.post(
            reverse("profiles:project_add", args=[self.alice_profile.pk]),
            {"project_name": "Persisted", "solution": "Kept it simple"},
        )
        self.client.logout()
        self.client.force_login(self.alice)
        response = self.client.get(reverse("profiles:projects", args=[self.alice_profile.pk]))
        self.assertContains(response, "Persisted")
