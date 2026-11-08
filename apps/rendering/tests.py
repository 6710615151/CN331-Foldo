"""Tests for portfolio templates and rendering (FOLDO-07)."""

import itertools
from datetime import date
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.profiles.models import MainProfile

from .selectors import (
    PortfolioContent,
    build_portfolio_content,
    education_item,
    experience_item,
    project_item,
    skill_item,
)
from .services import render_portfolio_html
from .themes import DEFAULT_THEME_KEY, THEMES, get_theme, theme_choices

PASSWORD = "pw-Foldo-12345"


class Rows:
    """Stands in for a related manager: ``.all()`` returns the rows."""

    def __init__(self, *rows):
        self.rows = list(rows)

    def all(self):
        return self.rows


def row(pk, **fields):
    return SimpleNamespace(pk=pk, **fields)


SKILLS = [row(1, name="Python", proficiency="advanced"), row(2, name="Figma", proficiency="beginner")]
EXPERIENCE = [
    row(10, job_title="Backend Intern", company="Acme", description="Built APIs.",
        start_date=date(2025, 6, 1), end_date=None),
]
EDUCATION = [
    row(20, institution="Thammasat University", degree="B.Eng.", field_of_study="Computer Engineering",
        start_date=date(2022, 8, 1), end_date=date(2026, 5, 1)),
]
STORY = SimpleNamespace(problem="Students re-type CVs.", role="Team lead", process="", solution="One profile.",
                        outcome="Saved hours.")
PROJECTS = [
    row(30, project_name="FOLDO", description="Portfolio builder.", project_url="https://example.com/foldo",
        start_date=date(2026, 1, 1), end_date=None, story=STORY,
        evidence=Rows(SimpleNamespace(caption="Demo video", evidence_type="video", file_url="https://example.com/v"))),
    row(31, project_name="Old project", description="", project_url="", start_date=None, end_date=None),
]


def providers(skills=(), experience=(), education=(), projects=()):
    data = {"skills": skills, "experience": experience, "education": education, "projects": projects}
    return {key: (lambda _profile, rows=rows: rows) for key, rows in data.items()}


def make_user(username):
    return get_user_model().objects.create_user(username=username, password=PASSWORD)


class ThemeRegistryTests(TestCase):
    def test_there_are_at_least_three_distinct_templates(self):
        self.assertGreaterEqual(len(THEMES), 3)
        self.assertEqual(len({t.key for t in THEMES}), len(THEMES))
        self.assertEqual(len({t.template_name for t in THEMES}), len(THEMES))

    def test_get_theme(self):
        self.assertEqual(get_theme("modern").name, "Modern")
        self.assertIsNone(get_theme("nope"))
        self.assertIsNotNone(get_theme(DEFAULT_THEME_KEY))

    def test_theme_choices_for_portfolio_versions(self):
        self.assertIn(("creative", "Creative"), theme_choices())


class AdapterTests(TestCase):
    """Model rows → SectionItem, tolerant of missing optional fields."""

    def test_experience_without_end_date_is_present(self):
        item = experience_item(EXPERIENCE[0])
        self.assertEqual(item.title, "Backend Intern")
        self.assertEqual(item.subtitle, "Acme")
        self.assertEqual(item.period, "Jun 2025 – Present")

    def test_education_joins_degree_and_field(self):
        item = education_item(EDUCATION[0])
        self.assertEqual(item.title, "B.Eng., Computer Engineering")
        self.assertEqual(item.subtitle, "Thammasat University")
        self.assertEqual(item.period, "Aug 2022 – May 2026")

    def test_skill_level_falls_back_to_raw_value(self):
        self.assertEqual(skill_item(SKILLS[0]).level, "advanced")

    def test_project_story_keeps_only_filled_fields_in_order(self):
        item = project_item(PROJECTS[0])
        self.assertEqual(
            [label for label, _ in item.story], ["Problem", "My role", "Solution", "Outcome"]
        )
        self.assertEqual(item.evidence, (("Demo video", "https://example.com/v"),))

    def test_project_without_story_or_evidence_still_works(self):
        item = project_item(PROJECTS[1])
        self.assertEqual(item.title, "Old project")
        self.assertEqual(item.story, ())
        self.assertEqual(item.evidence, ())
        self.assertEqual(item.period, "")

    def test_story_can_be_left_out(self):
        self.assertEqual(project_item(PROJECTS[0], include_story=False).story, ())

    def test_story_fields_stored_on_the_project_itself(self):
        """FOLDO-15 keeps problem/role/... on Project; there is no separate story row."""
        project = row(41, project_name="Inline", problem="P", role="", process="Q", solution="",
                      outcome="O")
        self.assertEqual(project_item(project).story, (("Problem", "P"), ("Process", "Q"), ("Outcome", "O")))

    def test_education_entry_with_years_level_and_grade(self):
        """apps.education rows: level + subject + years instead of degree + dates."""
        entry = SimpleNamespace(
            pk=50, institution="Thammasat University", subject="Computer Engineering", grade="3.75",
            start_year=2022, end_year=None, get_level_display=lambda: "Undergraduate degree",
        )
        item = education_item(entry)
        self.assertEqual(item.title, "Undergraduate degree, Computer Engineering")
        self.assertEqual(item.subtitle, "Thammasat University")
        self.assertEqual(item.period, "2022 – Present")
        self.assertEqual(item.note, "Grade: 3.75")

    def test_education_with_only_an_institution(self):
        item = education_item(row(51, institution="Some School"))
        self.assertEqual((item.title, item.subtitle, item.period, item.note), ("Some School", "", "", ""))

    def test_unsafe_links_are_dropped(self):
        project = row(40, project_name="X", project_url="javascript:alert(1)",
                      evidence=Rows(SimpleNamespace(caption="bad", file_url="data:text/html,hi")))
        item = project_item(project)
        self.assertEqual(item.url, "")
        self.assertEqual(item.evidence, ())


class BuildContentTests(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.profile = MainProfile.objects.create(owner=self.user, full_name="Alice Example")

    def build(self, **kwargs):
        kwargs.setdefault(
            "providers", providers(SKILLS, EXPERIENCE, EDUCATION, PROJECTS)
        )
        return build_portfolio_content(self.profile, **kwargs)

    def test_sections_in_display_order(self):
        keys = [s.key for s in self.build().sections]
        self.assertEqual(keys, ["experience", "education", "projects", "skills"])

    def test_empty_sections_are_left_out(self):
        content = self.build(providers=providers(skills=SKILLS))
        self.assertEqual([s.key for s in content.sections], ["skills"])

    def test_selection_keeps_only_chosen_items(self):
        content = self.build(selected={"skills": [2], "projects": [31]})
        self.assertEqual([s.key for s in content.sections], ["projects", "skills"])
        self.assertEqual([i.title for i in content.section("skills").items], ["Figma"])
        self.assertEqual([i.title for i in content.section("projects").items], ["Old project"])

    def test_empty_selection_means_nothing(self):
        self.assertEqual(self.build(selected={}).sections, ())

    def test_real_profile_without_section_models_renders_empty_sections(self):
        content = build_portfolio_content(self.profile)
        self.assertIsInstance(content, PortfolioContent)
        self.assertEqual(content.profile.display_name, "Alice Example")


class RenderAcrossCombinationsTests(TestCase):
    """Every template renders every mix of content without errors or empty headings."""

    def setUp(self):
        self.user = make_user("alice")
        self.full = MainProfile.objects.create(
            owner=self.user, label="Full", full_name="Alice Example", headline="Backend developer",
            bio="Line one\nLine two", location="Bangkok", contact_email="alice@example.com",
            phone="+66 81 234 5678", website="https://alice.dev", github_url="https://github.com/alice",
        )
        self.bare = MainProfile.objects.create(owner=self.user, label="Bare", full_name="Bare Bones")

    def test_every_theme_with_every_combination(self):
        section_sets = {
            "none": providers(),
            "skills only": providers(skills=SKILLS),
            "projects with story": providers(projects=PROJECTS),
            "everything": providers(SKILLS, EXPERIENCE, EDUCATION, PROJECTS),
        }
        for theme, profile, (label, provs), story in itertools.product(
            THEMES, (self.full, self.bare), section_sets.items(), (True, False)
        ):
            with self.subTest(theme=theme.key, profile=profile.label, sections=label, story=story):
                content = build_portfolio_content(profile, providers=provs, include_story=story)
                html = render_portfolio_html(theme, content)
                self.assertIn(profile.full_name, html)
                self.assertIn(f"pf--{theme.key}", html)
                for section in content.sections:
                    self.assertIn(f'id="pf-{section.key}"', html)
                for missing in {"experience", "education", "projects", "skills"} - {
                    s.key for s in content.sections
                }:
                    self.assertNotIn(f'id="pf-{missing}"', html)
                self.assertEqual("Team lead" in html, story and label in {"projects with story", "everything"})

    def test_missing_optional_fields_print_nothing(self):
        html = render_portfolio_html(get_theme("classic"), build_portfolio_content(self.bare, providers=providers()))
        self.assertNotIn('id="pf-about"', html)
        self.assertNotIn("pf-contact", html)
        self.assertNotIn("pf-headline", html)
        self.assertIn("ยังไม่มีเนื้อหาให้แสดง", html)

    def test_user_text_is_escaped_and_long_text_kept(self):
        long_word = "x" * 3000
        self.bare.bio = f"<script>alert('x')</script> {long_word}"
        self.bare.save()
        for theme in THEMES:
            with self.subTest(theme=theme.key):
                html = render_portfolio_html(theme, build_portfolio_content(self.bare, providers=providers()))
                self.assertNotIn("<script>alert", html)
                self.assertIn("&lt;script&gt;", html)
                self.assertIn(long_word, html)

    def test_bio_line_breaks_are_kept(self):
        html = render_portfolio_html(get_theme("classic"), build_portfolio_content(self.full, providers=providers()))
        self.assertIn("Line one<br>Line two", html)


class ViewTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice Example")
        self.bobs = MainProfile.objects.create(owner=self.bob, full_name="Bob Example")
        self.client.force_login(self.alice)

    def test_gallery_lists_templates_with_preview_links(self):
        response = self.client.get(reverse("rendering:gallery"))
        self.assertEqual(response.status_code, 200)
        for theme in THEMES:
            self.assertContains(response, theme.name)
            self.assertContains(response, reverse("rendering:preview", args=[theme.key, self.profile.pk]))

    def test_gallery_without_profile_asks_to_create_one(self):
        self.client.force_login(make_user("carol"))
        response = self.client.get(reverse("rendering:gallery"))
        self.assertContains(response, reverse("profiles:create"))
        self.assertNotContains(response, "/profiles/1/")

    def test_owner_can_preview_each_template(self):
        for theme in THEMES:
            with self.subTest(theme=theme.key):
                response = self.client.get(reverse("rendering:preview", args=[theme.key, self.profile.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Alice Example")
                self.assertContains(response, 'aria-current="page"')

    def test_another_users_profile_is_404(self):
        response = self.client.get(reverse("rendering:preview", args=["classic", self.bobs.pk]))
        self.assertEqual(response.status_code, 404)

    def test_unknown_template_is_404(self):
        response = self.client.get(reverse("rendering:preview", args=["neon", self.profile.pk]))
        self.assertEqual(response.status_code, 404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        for url in (reverse("rendering:gallery"), reverse("rendering:preview", args=["classic", self.profile.pk])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response, f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False
                )
