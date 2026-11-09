"""Duplicate a portfolio version, and pre-select a template from the gallery."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.portfolios.models import Portfolio, PortfolioContentSelection, PortfolioContentSetup
from apps.portfolios.quality.checks import ERROR, INFO, WARNING, Finding, QualityReport
from apps.profiles.models import MainProfile, Skill

PASSWORD = "pw-Foldo-12345"


class DuplicateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password=PASSWORD)
        self.bob = User.objects.create_user(username="bob", password=PASSWORD)
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice")
        self.skill = Skill.objects.create(profile=self.profile, name="Python")
        self.original = Portfolio.objects.create(
            owner=self.alice, title="Backend jobs", profile=self.profile, template_key="modern", is_published=True
        )
        PortfolioContentSetup.objects.create(portfolio=self.original)
        PortfolioContentSelection.objects.create(portfolio=self.original, section="skills", item_id=self.skill.pk)
        self.client.force_login(self.alice)
        self.url = reverse("portfolios:duplicate", args=[self.original.pk])

    def test_copy_is_private_with_same_settings_and_selection(self):
        response = self.client.post(self.url)
        copy = Portfolio.objects.exclude(pk=self.original.pk).get()
        self.assertRedirects(response, reverse("portfolios:update", args=[copy.pk]))
        self.assertEqual(copy.owner, self.alice)
        self.assertEqual(copy.title, "Backend jobs (สำเนา)")
        self.assertEqual(copy.profile, self.profile)
        self.assertEqual(copy.template_key, "modern")
        self.assertFalse(copy.is_published)
        self.assertNotEqual(copy.slug, self.original.slug)
        self.assertTrue(PortfolioContentSetup.objects.filter(portfolio=copy).exists())
        self.assertEqual(
            list(copy.content_selections.values_list("section", "item_id")), [("skills", self.skill.pk)]
        )
        self.original.refresh_from_db()
        self.assertTrue(self.original.is_published)

    def test_uncustomised_version_copies_as_uncustomised(self):
        plain = Portfolio.objects.create(owner=self.alice, title="Plain")
        self.client.post(reverse("portfolios:duplicate", args=[plain.pk]))
        copy = Portfolio.objects.get(title="Plain (สำเนา)")
        self.assertFalse(PortfolioContentSetup.objects.filter(portfolio=copy).exists())

    def test_long_titles_still_fit(self):
        self.original.title = "x" * 120
        self.original.save()
        self.client.post(self.url)
        copy = Portfolio.objects.exclude(pk=self.original.pk).get()
        self.assertLessEqual(len(copy.title), 120)
        self.assertTrue(copy.title.endswith("(สำเนา)"))

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Portfolio.objects.count(), 1)

    def test_other_users_cannot_duplicate(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertEqual(Portfolio.objects.count(), 1)

    def test_list_offers_duplicate(self):
        self.assertContains(self.client.get(reverse("portfolios:list")), self.url)


class TemplatePreselectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password=PASSWORD)
        self.client.force_login(self.user)

    def test_known_template_is_preselected(self):
        html = self.client.get(reverse("portfolios:create") + "?template=creative").content.decode()
        self.assertRegex(html, r'value="creative"[^>]*checked')

    def test_unknown_template_is_ignored(self):
        response = self.client.get(reverse("portfolios:create") + "?template=<script>")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>\"")

    def test_gallery_links_to_create_with_template(self):
        self.assertContains(self.client.get(reverse("rendering:gallery")), reverse("portfolios:create") + "?template=modern")


class QualityScoreTests(TestCase):
    def report(self, *severities):
        return QualityReport(findings=tuple(Finding(s, "t", "d") for s in severities), checked_at=None)

    def test_clean_report_scores_100(self):
        self.assertEqual(self.report().score, 100)

    def test_warnings_and_infos_lower_the_score(self):
        self.assertEqual(self.report(WARNING, INFO).score, 90)

    def test_blocking_report_stays_below_50(self):
        self.assertLess(self.report(ERROR).score, 50)
        self.assertEqual(self.report(*[ERROR] * 6).score, 0)
