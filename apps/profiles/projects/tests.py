"""Tests for projects and Project Story (FOLDO-04, FOLDO-15)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.test import TestCase

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