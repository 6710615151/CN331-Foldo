"""FOLDO-07: each portfolio version renders its own content in its own template.

Uses the real models (Skill, Experience, Project + story, Education), so a
change in any of them that breaks rendering fails here.
"""
import importlib
from datetime import date

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.profiles.models import Education, Experience, MainProfile, Project, Skill
from apps.rendering.themes import DEFAULT_THEME_KEY, THEMES

from .models import Portfolio
from .services import build_version_content, render_version_html, selected_ids

User = get_user_model()
PASSWORD = "pass-12345"
SECTION_KEYS = {"experience", "education", "projects", "skills"}


def section_keys(content):
    return {section.key for section in content.sections}


def titles(content, key):
    section = content.section(key)
    return [item.title for item in section.items] if section else []


class VersionRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password=PASSWORD)
        cls.bob = User.objects.create_user("bob", password=PASSWORD)
        cls.profile = MainProfile.objects.create(
            owner=cls.alice, full_name="Alice Doe", headline="Backend developer", is_default=True,
            bio="Hello", contact_email="alice@example.com",
        )
        cls.python = Skill.objects.create(profile=cls.profile, name="Python", proficiency="advanced")
        cls.figma = Skill.objects.create(profile=cls.profile, name="Figma", proficiency="beginner")
        cls.job = Experience.objects.create(
            profile=cls.profile, company="Acme", job_title="Backend Intern", start_date=date(2025, 6, 1),
        )
        cls.foldo = Project.objects.create(
            profile=cls.profile, project_name="FOLDO", description="Portfolio builder.",
            project_url="https://example.com/foldo", start_date=date(2026, 1, 1),
            problem="Students re-type CVs.", role="Team lead", solution="One profile, many portfolios.",
        )
        cls.old = Project.objects.create(profile=cls.profile, project_name="Old project")
        cls.uni = Education.objects.create(
            profile=cls.profile, institution="Thammasat University", degree="B.Eng.",
            field_of_study="Computer Engineering", grade="3.75", start_date=date(2022, 8, 1),
        )

        cls.backend = Portfolio.objects.create(owner=cls.alice, title="Backend jobs", template_key="modern")
        cls.design = Portfolio.objects.create(owner=cls.alice, title="Design jobs", template_key="creative")

    def setUp(self):
        self.client.login(username="alice", password=PASSWORD)

    def preview(self, portfolio):
        return self.client.get(reverse("portfolios:preview", args=[portfolio.pk]))

    # --- one template per version -------------------------------------------

    def test_each_version_renders_in_its_own_template(self):
        backend, design = self.preview(self.backend), self.preview(self.design)
        self.assertContains(backend, 'class="pf pf--modern"')
        self.assertNotContains(backend, "pf--creative")
        self.assertContains(design, 'class="pf pf--creative"')
        self.assertNotContains(design, "pf--modern")

    def test_every_template_renders_every_section_from_real_models(self):
        for theme in THEMES:
            with self.subTest(theme=theme.key):
                self.backend.template_key = theme.key
                html = render_version_html(self.backend, preview=True)
                self.assertIn(f"pf--{theme.key}", html)
                for key in SECTION_KEYS:
                    self.assertIn(f'id="pf-{key}"', html)
                for text in ("Alice Doe", "Backend Intern", "Python", "Advanced", "FOLDO",
                             "Thammasat University", "Grade: 3.75", "Team lead",
                             "One profile, many portfolios."):
                    self.assertIn(text, html)

    def test_changing_one_versions_template_leaves_the_other_alone(self):
        response = self.client.post(reverse("portfolios:update", args=[self.backend.pk]), {
            "title": "Backend jobs", "profile": "", "template_key": "classic",
        })
        self.assertEqual(response.status_code, 302)
        self.backend.refresh_from_db()
        self.design.refresh_from_db()
        self.assertEqual(self.backend.template_key, "classic")
        self.assertEqual(self.design.template_key, "creative")

    def test_retired_or_unknown_stored_key_still_renders_with_the_default(self):
        Portfolio.objects.filter(pk=self.backend.pk).update(template_key="midnight")
        response = self.preview(self.backend)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"pf--{DEFAULT_THEME_KEY}")

    # --- content per section -------------------------------------------------

    def test_project_story_fields_render_in_order_and_empty_ones_are_skipped(self):
        project = build_version_content(self.backend).section("projects").items[0]
        self.assertEqual(project.title, "FOLDO")
        self.assertEqual([label for label, _ in project.story], ["Problem", "My role", "Solution"])
        old = build_version_content(self.backend).section("projects").items[1]
        self.assertEqual(old.story, ())

    def test_education_comes_from_the_versions_profile(self):
        content = build_version_content(self.backend)
        self.assertEqual(titles(content, "education"), ["B.Eng., Computer Engineering"])
        self.assertEqual(content.section("education").items[0].id, self.uni.pk)  # real id, so FOLDO-06 can select it

    def test_version_without_any_profile_renders_an_empty_page(self):
        carol = User.objects.create_user("carol", password=PASSWORD)
        portfolio = Portfolio.objects.create(owner=carol, title="Empty")
        html = render_version_html(portfolio, preview=True)
        self.assertIn("ยังไม่มีเนื้อหาให้แสดง", html)
        self.assertIn("carol", html)
        for key in SECTION_KEYS:
            self.assertNotIn(f'id="pf-{key}"', html)

    def test_long_text_is_kept_and_user_text_is_escaped(self):
        long_text = "word " * 900 + "x" * 600  # ~5000 characters, one very long word
        Project.objects.filter(pk=self.foldo.pk).update(
            description=long_text, role="<script>alert('x')</script>",
        )
        for theme in THEMES:
            with self.subTest(theme=theme.key):
                self.backend.template_key = theme.key
                html = render_version_html(self.backend)
                self.assertIn("x" * 600, html)
                self.assertNotIn("<script>alert", html)
                self.assertIn("&lt;script&gt;", html)

    # --- per-version selection (FOLDO-06 contract) ----------------------------

    def test_never_customised_version_shows_everything(self):
        self.assertIsNone(selected_ids(self.backend))
        self.assertEqual(section_keys(build_version_content(self.backend)), SECTION_KEYS)

    def test_selection_keeps_only_chosen_items(self):
        content = build_version_content(self.backend, selected={
            "skills": {self.python.pk}, "projects": {self.old.pk}, "education": {self.uni.pk},
        })
        self.assertEqual(section_keys(content), {"skills", "projects", "education"})
        self.assertEqual(titles(content, "skills"), ["Python"])
        self.assertEqual(titles(content, "projects"), ["Old project"])

    def test_empty_selection_shows_only_the_identity(self):
        content = build_version_content(self.backend, selected={})
        self.assertEqual(content.sections, ())
        self.assertEqual(content.profile.display_name, "Alice Doe")

    def test_selecting_in_one_version_does_not_change_another_or_the_sources(self):
        build_version_content(self.backend, selected={"skills": {self.python.pk}})
        self.assertEqual(titles(build_version_content(self.design), "skills"), ["Figma", "Python"])
        self.assertEqual(Skill.objects.filter(profile=self.profile).count(), 2)
        self.assertEqual(Project.objects.filter(profile=self.profile).count(), 2)

    def test_another_users_ids_in_a_selection_are_ignored(self):
        bobs = MainProfile.objects.create(owner=self.bob, full_name="Bob", is_default=True)
        bob_skill = Skill.objects.create(profile=bobs, name="Secret skill")
        content = build_version_content(self.backend, selected={"skills": {bob_skill.pk}})
        self.assertNotIn("Secret skill", render_version_html(self.backend))
        self.assertIsNone(content.section("skills"))

    # --- preview vs public ----------------------------------------------------

    def test_owner_preview_has_the_bar_and_noindex(self):
        response = self.preview(self.backend)
        self.assertContains(response, "ส่วนตัว เห็นได้เฉพาะคุณ")
        self.assertContains(response, reverse("portfolios:update", args=[self.backend.pk]))
        self.assertContains(response, '<meta name="robots" content="noindex">')

    def test_device_frame_has_no_bar_but_is_noindex(self):
        response = self.client.get(reverse("portfolios:preview_frame", args=[self.backend.pk]))
        self.assertContains(response, "pf--modern")
        self.assertNotContains(response, "pf-toolbar")
        self.assertContains(response, '<meta name="robots" content="noindex">')

    def test_public_page_only_when_published_and_without_owner_tools(self):
        self.client.logout()
        url = reverse("portfolios:public", args=[self.backend.slug])
        self.assertEqual(self.client.get(url).status_code, 404)
        Portfolio.objects.filter(pk=self.backend.pk).update(is_published=True)
        response = self.client.get(url)
        self.assertContains(response, "pf--modern")
        self.assertNotContains(response, "pf-toolbar")
        self.assertNotContains(response, "noindex")

    def test_previewing_never_publishes(self):
        self.preview(self.backend)
        self.backend.refresh_from_db()
        self.assertFalse(self.backend.is_published)

    def test_another_users_version_is_404(self):
        self.client.logout()
        self.client.login(username="bob", password=PASSWORD)
        self.assertEqual(self.preview(self.backend).status_code, 404)


class TemplatePickerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password=PASSWORD)
        MainProfile.objects.create(owner=cls.alice, full_name="Alice Doe", is_default=True)

    def setUp(self):
        self.client.login(username="alice", password=PASSWORD)

    def test_create_form_offers_every_template_as_a_card(self):
        response = self.client.get(reverse("portfolios:create"))
        for theme in THEMES:
            self.assertContains(response, f'value="{theme.key}"')
            self.assertContains(response, theme.description)
        self.assertRegex(
            response.content.decode(),
            rf'value="{DEFAULT_THEME_KEY}"\s+id="id_template_key_{DEFAULT_THEME_KEY}" checked',
        )
        self.assertContains(response, reverse("rendering:gallery"))

    def test_chosen_template_is_saved(self):
        self.client.post(reverse("portfolios:create"), {"title": "Design", "profile": "", "template_key": "creative"})
        self.assertEqual(Portfolio.objects.get(title="Design").template_key, "creative")

    def test_unknown_template_is_rejected_and_kept_unsaved(self):
        response = self.client.post(reverse("portfolios:create"), {"title": "X", "profile": "", "template_key": "neon"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(Portfolio.objects.exists())


class LegacyTemplateMigrationTests(TestCase):
    def test_old_colour_layouts_move_to_the_closest_template(self):
        migration = importlib.import_module("apps.portfolios.migrations.0003_rendering_themes")
        alice = User.objects.create_user("alice", password=PASSWORD)
        keys = ["classic", "midnight", "ocean", "mono", "something-else"]
        for key in keys:
            Portfolio.objects.create(owner=alice, title=key)
        for key in keys:  # bypass field choices, as old rows would
            Portfolio.objects.filter(title=key).update(template_key=key)

        migration.forwards(django_apps, None)

        result = dict(Portfolio.objects.values_list("title", "template_key"))
        self.assertEqual(result, {
            "classic": "classic", "midnight": "modern", "ocean": "creative",
            "mono": "classic", "something-else": "classic",
        })


class MoveEducationMigrationTests(TestCase):
    """portfolios.0005 copies the retired per-user education rows into profiles.Education."""

    def setUp(self):
        from django.db import connection

        self.connection = connection
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE education_educationentry (id integer PRIMARY KEY, owner_id integer, "
                "level varchar(20), institution varchar(150), subject varchar(150), grade varchar(40), "
                "start_year integer NULL, end_year integer NULL, created_at datetime, updated_at datetime)"
            )
        self.alice = User.objects.create_user("alice", password=PASSWORD)
        self.carol = User.objects.create_user("carol", password=PASSWORD)  # no profile
        MainProfile.objects.create(owner=self.alice, full_name="Alice", label="Other")
        self.default = MainProfile.objects.create(owner=self.alice, full_name="Alice", label="Main", is_default=True)
        self.portfolio = Portfolio.objects.create(owner=self.alice, title="v1")

    def insert(self, *rows):
        with self.connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    "INSERT INTO education_educationentry VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
                    "'2026-01-01 00:00:00', '2026-01-01 00:00:00')",
                    row,
                )

    def run_migration(self):
        from types import SimpleNamespace

        migration = importlib.import_module("apps.portfolios.migrations.0005_move_education_to_profiles")
        cursor = self.connection.cursor()
        migration.forwards(django_apps, SimpleNamespace(connection=self.connection, execute=cursor.execute))

    def test_rows_move_to_the_default_profile_and_selections_follow(self):
        from .models import PortfolioContentSelection

        self.insert(
            (7, self.alice.pk, "undergraduate", "Thammasat University", "Computer Engineering", "3.75", 2022, None),
            (8, self.alice.pk, "high_school", "", "", "", None, None),          # blank: never shown
            (9, self.carol.pk, "phd", "Somewhere", "", "", 2020, 2024),        # no profile to hold it
            (10, self.alice.pk, "graduate", "", "AI", "", 2027, 2025),         # end before start
        )
        PortfolioContentSelection.objects.create(portfolio=self.portfolio, section="education", item_id=7)
        PortfolioContentSelection.objects.create(portfolio=self.portfolio, section="education", item_id=8)

        self.run_migration()

        moved = Education.objects.filter(profile=self.default).order_by("start_date")
        self.assertEqual(
            [(e.institution, e.degree, e.field_of_study, e.grade, e.start_date, e.end_date) for e in moved],
            [
                ("Thammasat University", "Undergraduate degree", "Computer Engineering", "3.75",
                 date(2022, 1, 1), None),
                ("Graduate degree (Master's)", "Graduate degree (Master's)", "AI", "", date(2027, 1, 1), None),
            ],
        )
        self.assertEqual(Education.objects.count(), 2)
        uni = moved.first()
        self.assertEqual(
            list(PortfolioContentSelection.objects.filter(section="education").values_list("item_id", flat=True)),
            [uni.pk],
        )
        self.assertNotIn("education_educationentry", self.connection.introspection.table_names())

    def test_does_nothing_without_the_old_table(self):
        with self.connection.cursor() as cursor:
            cursor.execute("DROP TABLE education_educationentry")
        self.run_migration()
        self.assertFalse(Education.objects.exists())
