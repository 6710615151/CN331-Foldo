"""Tests for Portfolio DNA (FOLDO-14): which portfolio versions reuse each item."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.profiles.models import Education, Experience, MainProfile, Project, Skill
from apps.portfolios.models import Portfolio

from .dna import build_dna, compute_dna
from .sources import VersionRef, portfolio_versions, source_sections

PASSWORD = "pw-Foldo-12345"


def make_user(username):
    return get_user_model().objects.create_user(username=username, password=PASSWORD)


class DnaBuildTests(TestCase):
    """build_dna against real models: the exact bug that 500'd in manual testing."""

    def setUp(self):
        self.user = make_user("alice")
        self.profile = MainProfile.objects.create(owner=self.user, full_name="Alice")

    def test_build_dna_with_no_data_and_no_portfolios_does_not_crash(self):
        dna = build_dna(self.profile)
        self.assertEqual(dna.total_items, 0)
        self.assertEqual(dna.versions, ())

    def test_item_with_no_portfolio_is_unused(self):
        Skill.objects.create(profile=self.profile, name="Python")
        dna = build_dna(self.profile)
        self.assertEqual(len(dna.unused_items), 1)
        self.assertEqual(dna.unused_items[0].item.title, "Python")

    def test_portfolio_with_no_selection_uses_everything(self):
        """selected_ids() is None until FOLDO-06 configures a selection -> 'uses everything'."""
        Skill.objects.create(profile=self.profile, name="Python")
        Experience.objects.create(
            profile=self.profile, company="Acme", job_title="Dev", start_date="2024-01-01"
        )
        Portfolio.objects.create(owner=self.user, profile=self.profile, title="Career")

        dna = build_dna(self.profile)
        self.assertEqual(dna.unused_items, [])
        self.assertEqual(len(dna.reused_items), 0)
        for row in dna.rows:
            self.assertEqual(len(row.used_in), 1)
            self.assertEqual(row.used_in[0].name, "Career")

    def test_two_portfolios_both_use_the_same_item(self):
        Skill.objects.create(profile=self.profile, name="Python")
        Portfolio.objects.create(owner=self.user, profile=self.profile, title="Career")
        Portfolio.objects.create(owner=self.user, profile=self.profile, title="Creative")

        dna = build_dna(self.profile)
        self.assertEqual(len(dna.reused_items), 1)
        self.assertEqual({v.name for v in dna.reused_items[0].used_in}, {"Career", "Creative"})

    def test_portfolio_for_another_profile_is_not_counted(self):
        bob = make_user("bob")
        bobs_profile = MainProfile.objects.create(owner=bob, full_name="Bob")
        Skill.objects.create(profile=self.profile, name="Python")
        Portfolio.objects.create(owner=bob, profile=bobs_profile, title="Bob's version")

        dna = build_dna(self.profile)
        self.assertEqual(dna.versions, ())
        self.assertEqual(len(dna.unused_items), 1)

    def test_portfolio_without_a_chosen_profile_falls_back_to_the_default(self):
        """profile=None on Portfolio means 'follow my default profile' (apps.portfolios.services)."""
        Skill.objects.create(profile=self.profile, name="Python")
        Portfolio.objects.create(owner=self.user, profile=None, title="Follows default")

        dna = build_dna(self.profile)
        self.assertEqual(len(dna.versions), 1)
        self.assertEqual(dna.versions[0].name, "Follows default")

    def test_education_experience_and_project_all_appear(self):
        Education.objects.create(profile=self.profile, institution="TU", start_date="2020-01-01")
        Experience.objects.create(
            profile=self.profile, company="Acme", job_title="Dev", start_date="2024-01-01"
        )
        Project.objects.create(profile=self.profile, project_name="FOLDO")
        dna = build_dna(self.profile)
        self.assertEqual(dna.total_items, 3)
        keys = {s.key for s in dna.sections if s.rows}
        self.assertEqual(keys, {"education", "experience", "projects"})

    def test_untitled_project_still_appears(self):
        Project.objects.create(profile=self.profile, project_name="")
        dna = build_dna(self.profile)
        self.assertEqual(dna.total_items, 1)
        self.assertIn("untitled", dna.rows[0].item.title)


class ComputeDnaUnitTests(TestCase):
    """Pure-logic tests against fake sections/versions, no DB needed."""

    def section(self, key, title, item_ids):
        from .sources import SourceItem

        items = [SourceItem(section=key, id=i, title=f"item-{i}", edit_url="/x/") for i in item_ids]
        return (key, title, items)

    def test_explicit_empty_selection_means_nothing_is_used(self):
        sections = [self.section("skills", "Skills", [1, 2])]
        version = VersionRef(id=1, name="V1", url="/v/1/", selected={"skills": frozenset()})
        report = compute_dna(sections, [version])
        self.assertEqual(len(report.unused_items), 2)

    def test_stale_selection_pointing_at_a_deleted_item_is_reported(self):
        sections = [self.section("skills", "Skills", [1])]
        version = VersionRef(id=1, name="V1", url="/v/1/", selected={"skills": frozenset({1, 999})})
        report = compute_dna(sections, [version])
        self.assertEqual(len(report.missing), 1)
        self.assertEqual(report.missing[0].item_id, 999)

    def test_none_selection_never_produces_a_missing_entry(self):
        sections = [self.section("skills", "Skills", [1])]
        version = VersionRef(id=1, name="V1", url="/v/1/", selected=None)
        report = compute_dna(sections, [version])
        self.assertEqual(report.missing, ())


class PortfolioVersionsSourceTests(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.profile = MainProfile.objects.create(owner=self.user, full_name="Alice")

    def test_returns_empty_list_for_a_profile_with_no_portfolios(self):
        self.assertEqual(portfolio_versions(self.profile), [])

    def test_version_ref_carries_the_template_key(self):
        Portfolio.objects.create(
            owner=self.user, profile=self.profile, title="Career", template_key="modern"
        )
        [version] = portfolio_versions(self.profile)
        self.assertEqual(version.template, "modern")

    def test_source_sections_lists_every_section_even_when_empty(self):
        sections = source_sections(self.profile)
        keys = [key for key, _, _ in sections]
        self.assertEqual(set(keys), {"experience", "education", "projects", "skills"})


class PortfolioDnaViewTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice")
        self.bobs_profile = MainProfile.objects.create(owner=self.bob, full_name="Bob Secret")
        self.url = reverse("insights:dna", args=[self.profile.pk])
        self.client.force_login(self.alice)

    def test_owner_sees_their_dna_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_page_renders_with_a_skill_and_a_portfolio_without_crashing(self):
        """Regression test for the 500 crash: dead code in portfolio_versions_for_profile."""
        Skill.objects.create(profile=self.profile, name="Python")
        Portfolio.objects.create(owner=self.alice, profile=self.profile, title="Career")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python")
        self.assertContains(response, "Career")

    def test_another_users_profile_is_404(self):
        response = self.client.get(reverse("insights:dna", args=[self.bobs_profile.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Bob Secret", status_code=404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={self.url}", fetch_redirect_response=False
        )

    def test_viewing_dna_changes_nothing(self):
        Skill.objects.create(profile=self.profile, name="Python")
        before = MainProfile.objects.get(pk=self.profile.pk).updated_at
        self.client.get(self.url)
        self.assertEqual(MainProfile.objects.get(pk=self.profile.pk).updated_at, before)

    def test_dashboard_links_to_dna(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertContains(response, self.url)
