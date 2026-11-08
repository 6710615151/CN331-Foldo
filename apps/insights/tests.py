"""Tests for Portfolio DNA (FOLDO-14)."""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.profiles.models import MainProfile

from .dna import build_dna, compute_dna
from .sources import SourceItem, VersionRef, portfolio_versions, source_sections

PASSWORD = "pw-Foldo-12345"


def make_user(username):
    return get_user_model().objects.create_user(username=username, password=PASSWORD)


def row(pk, **fields):
    return SimpleNamespace(pk=pk, **fields)


def providers(**sections):
    keys = ("skills", "experience", "education", "projects")
    return {key: (lambda _p, rows=sections.get(key, ()): rows) for key in keys}


def version(pk, name, **selected):
    return VersionRef(id=pk, name=name, url=f"/v/{pk}/",
                      selected={k: frozenset(v) for k, v in selected.items()})


def item(section, pk, title):
    return SourceItem(section=section, id=pk, title=title, edit_url=f"/edit/{section}/{pk}/")


class ComputeDnaTests(TestCase):
    def setUp(self):
        self.sections = [
            ("skills", "Skills", [item("skills", 1, "Python"), item("skills", 2, "Figma")]),
            ("projects", "Projects", [item("projects", 10, "FOLDO")]),
        ]
        self.career = version(100, "Career", skills={1}, projects={10})
        self.creative = version(101, "Creative", skills={2}, projects={10})

    def test_each_item_lists_the_versions_that_use_it(self):
        dna = compute_dna(self.sections, [self.career, self.creative])
        used = {row.item.title: [v.name for v in row.used_in] for row in dna.rows}
        self.assertEqual(used, {"Python": ["Career"], "Figma": ["Creative"], "FOLDO": ["Career", "Creative"]})

    def test_unused_and_reused_items_are_discoverable(self):
        dna = compute_dna(self.sections, [self.career])
        self.assertEqual([r.item.title for r in dna.unused_items], ["Figma"])
        dna = compute_dna(self.sections, [self.career, self.creative])
        self.assertEqual([r.item.title for r in dna.reused_items], ["FOLDO"])

    def test_without_versions_everything_is_unused(self):
        dna = compute_dna(self.sections, [])
        self.assertEqual(len(dna.unused_items), dna.total_items)

    def test_same_id_in_another_section_is_not_confused(self):
        version_with_skill_10 = version(102, "Odd", skills={10})
        dna = compute_dna(self.sections, [version_with_skill_10])
        project_row = dna.sections[1].rows[0]
        self.assertTrue(project_row.is_unused)

    def test_selection_of_a_deleted_item_is_reported_not_hidden(self):
        stale = version(103, "Stale", skills={1, 99})
        dna = compute_dna(self.sections, [stale])
        self.assertEqual([(m.version.name, m.section, m.item_id) for m in dna.missing], [("Stale", "skills", 99)])
        python = dna.sections[0].rows[0]
        self.assertEqual([v.name for v in python.used_in], ["Stale"])

    def test_removing_an_item_from_one_version_keeps_source_and_other_versions(self):
        before = compute_dna(self.sections, [self.career, self.creative])
        career_without_project = version(100, "Career", skills={1})
        after = compute_dna(self.sections, [career_without_project, self.creative])
        self.assertEqual(before.total_items, after.total_items)
        foldo = next(r for r in after.rows if r.item.title == "FOLDO")
        self.assertEqual([v.name for v in foldo.used_in], ["Creative"])


class SourceTests(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.profile = MainProfile.objects.create(owner=self.user, full_name="Alice")

    def test_source_sections_lists_every_section_with_edit_links(self):
        sections = source_sections(self.profile, providers(skills=[row(1, name="Python")]))
        self.assertEqual([key for key, _, _ in sections], ["experience", "education", "projects", "skills"])
        skills = sections[-1][2]
        self.assertEqual(skills[0].title, "Python")
        self.assertTrue(skills[0].edit_url.startswith("/"))

    def test_missing_edit_page_falls_back_to_the_profile(self):
        sections = source_sections(self.profile, providers(education=[row(5, institution="TU")]))
        education = dict((k, items) for k, _, items in sections)["education"]
        self.assertEqual(education[0].edit_url, reverse("profiles:view", args=[self.profile.pk]))

    def test_untitled_rows_still_show(self):
        sections = source_sections(self.profile, providers(projects=[row(7)]))
        projects = dict((k, items) for k, _, items in sections)["projects"]
        self.assertEqual(projects[0].title, "(untitled #7)")

    def test_versions_are_read_from_the_agreed_relation(self):
        selections = SimpleNamespace(all=lambda: [
            SimpleNamespace(content_type="skills", content_id=1),
            SimpleNamespace(content_type="projects", content_id=10),
        ])
        fake_profile = SimpleNamespace(portfolio_versions=SimpleNamespace(all=lambda: [
            SimpleNamespace(pk=5, version_name="Career", selections=selections),
        ]))
        [ref] = portfolio_versions(fake_profile)
        self.assertEqual(ref.name, "Career")
        self.assertTrue(ref.uses("skills", 1))
        self.assertTrue(ref.uses("projects", 10))
        self.assertFalse(ref.uses("skills", 10))

    def test_no_versions_relation_yet_means_no_versions(self):
        self.assertEqual(portfolio_versions(self.profile), [])

    def test_build_dna_on_a_real_profile(self):
        dna = build_dna(self.profile, providers=providers(skills=[row(1, name="Python")]))
        self.assertEqual(dna.total_items, 1)
        self.assertEqual(dna.versions, ())


class DnaViewTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice")
        self.bobs = MainProfile.objects.create(owner=self.bob, full_name="Bob Secret")
        self.url = reverse("insights:dna", args=[self.profile.pk])
        self.client.force_login(self.alice)

    def test_owner_sees_their_dna(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portfolio DNA")
        self.assertEqual(response.context["dna"].total_items, 0)
        self.assertContains(response, "โปรไฟล์นี้ยังไม่มี")

    def test_another_users_dna_is_404_and_leaks_nothing(self):
        response = self.client.get(reverse("insights:dna", args=[self.bobs.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Bob Secret", status_code=404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}", fetch_redirect_response=False)

    def test_viewing_dna_changes_nothing(self):
        before = MainProfile.objects.get(pk=self.profile.pk).updated_at
        self.client.get(self.url)
        self.assertEqual(MainProfile.objects.get(pk=self.profile.pk).updated_at, before)

    def test_dashboard_links_to_dna(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertContains(response, self.url)
