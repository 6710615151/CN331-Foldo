"""Edge cases and failure paths for portfolios, PDF export, quality check,
content selection and Portfolio DNA sources."""

import builtins
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.insights import sources as dna_sources
from apps.portfolios import pdf
from apps.portfolios.content_selection.selectors import get_selected_ids
from apps.portfolios.content_selection.sources import available_items
from apps.portfolios.models import Portfolio, PortfolioContentSelection, PortfolioContentSetup
from apps.portfolios.quality import checks
from apps.portfolios.services import get_portfolios
from apps.profiles.models import MainProfile, Skill

PASSWORD = "pw-Foldo-12345"


class _Owner(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="owner", password=PASSWORD)
        self.client.force_login(self.user)

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class ModelTests(_Owner):
    def test_string_forms_and_urls(self):
        portfolio = Portfolio.objects.create(owner=self.user, title="Backend")
        setup = PortfolioContentSetup.objects.create(portfolio=portfolio)
        row = PortfolioContentSelection.objects.create(portfolio=portfolio, section="skills", item_id=3)
        self.assertEqual(str(portfolio), "Backend (owner)")
        self.assertEqual(portfolio.get_absolute_url(), reverse("portfolios:preview", args=[portfolio.pk]))
        self.assertEqual(str(setup), f"Content chosen for {portfolio.pk}")
        self.assertEqual(str(row), f"skills:3 in {portfolio.pk}")

    def test_slug_collision_retries_with_a_new_suffix(self):
        Portfolio.objects.create(owner=self.user, title="Same", slug="same-aaaaaa")
        hexes = iter(["aaaaaa" + "0" * 26, "bbbbbb" + "0" * 26])
        with mock.patch("apps.portfolios.models.uuid.uuid4", side_effect=lambda: mock.Mock(hex=next(hexes))):
            second = Portfolio.objects.create(owner=self.user, title="Same")
        self.assertEqual(second.slug, "same-bbbbbb")

    def test_anonymous_users_have_no_portfolios(self):
        from django.contrib.auth.models import AnonymousUser

        Portfolio.objects.create(owner=self.user, title="Mine")
        self.assertFalse(get_portfolios(AnonymousUser()).exists())
        self.assertFalse(get_portfolios(None).exists())


class ViewFailureTests(_Owner):
    def setUp(self):
        super().setUp()
        self.portfolio = Portfolio.objects.create(owner=self.user, title="V1")

    def test_duplicate_failure_keeps_the_user_on_the_list_with_a_message(self):
        with mock.patch("apps.portfolios.views.duplicate_portfolio", side_effect=DatabaseError):
            response = self.client.post(reverse("portfolios:duplicate", args=[self.portfolio.pk]))
        self.assertRedirects(response, reverse("portfolios:list"))
        self.assertIn("ทำสำเนาไม่สำเร็จ ลองอีกครั้ง", self.messages(response))
        self.assertEqual(Portfolio.objects.count(), 1)

    def test_pdf_unavailable_without_javascript_redirects_with_a_message(self):
        with mock.patch("apps.portfolios.views.render_pdf", side_effect=pdf.PdfUnavailable("no pango")):
            response = self.client.get(reverse("portfolios:pdf", args=[self.portfolio.pk]))
        self.assertRedirects(response, reverse("portfolios:list"))
        self.assertTrue(any("ยังสร้าง PDF ไม่ได้" in m for m in self.messages(response)))


class PdfFetcherTests(TestCase):
    """The PDF renderer may read local static/media files and web fonts — nothing else."""

    def setUp(self):
        self.default = mock.Mock(return_value={"string": b""})
        self.fetch = pdf._make_fetcher(self.default)

    def test_data_urls_and_font_hosts_use_the_default_fetcher(self):
        self.fetch("data:text/plain,hi")
        self.fetch("https://fonts.googleapis.com/css2?family=Inter")
        self.assertEqual(self.default.call_count, 2)

    def test_other_hosts_are_blocked(self):
        with self.assertRaisesMessage(ValueError, "Blocked resource"):
            self.fetch("https://evil.example/steal.css")
        self.default.assert_not_called()

    def test_local_static_files_are_read_from_disk(self):
        result = self.fetch("http://pdf.local/static/css/styles.css")
        self.addCleanup(result["file_obj"].close)
        self.assertEqual(result["mime_type"], "text/css")

    def test_missing_local_file_is_an_error(self):
        with self.assertRaisesMessage(ValueError, "File not found"):
            self.fetch("http://pdf.local/static/css/does-not-exist.css")

    def test_static_finder_errors_and_list_results(self):
        with mock.patch.object(pdf.finders, "find", side_effect=Exception("escape")):
            self.assertIsNone(pdf._local_file("/static/../../etc/passwd"))
        with mock.patch.object(pdf.finders, "find", return_value=["/tmp/a.css"]):
            self.assertEqual(pdf._local_file("/static/a.css"), Path("/tmp/a.css"))
        with mock.patch.object(pdf.finders, "find", return_value=[]):
            self.assertIsNone(pdf._local_file("/static/a.css"))

    def test_media_files_only_inside_media_root(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            Path(media, "p.png").write_bytes(b"x")
            self.assertEqual(pdf._local_file("/media/p.png"), Path(media, "p.png").resolve())
            self.assertIsNone(pdf._local_file("/media/../../etc/passwd"))
            self.assertIsNone(pdf._local_file("/other/p.png"))

    def test_missing_weasyprint_is_reported_as_unavailable(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise OSError("cannot load library 'pango'")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(pdf.PdfUnavailable):
                pdf.render_pdf(mock.Mock(), request=None)


class QualityCheckEdgeTests(_Owner):
    def test_first_url_skips_routes_that_do_not_exist(self):
        self.assertEqual(checks._first_url(("nope:missing", []), ("portfolios:list", [])), reverse("portfolios:list"))
        self.assertEqual(checks._first_url(("nope:missing", [])), "")

    def test_unreadable_content_is_reported_not_crashed(self):
        MainProfile.objects.create(owner=self.user, full_name="A")
        portfolio = Portfolio.objects.create(owner=self.user, title="V")
        with mock.patch.object(checks, "build_version_content", side_effect=RuntimeError("boom")):
            report = checks.run_quality_check(portfolio)
        self.assertIn("อ่านข้อมูลของพอร์ตโฟลิโอนี้ไม่สำเร็จ", [f.title for f in report.errors])


class ContentSelectionEdgeTests(_Owner):
    def test_owner_without_a_profile_has_nothing_to_choose(self):
        portfolio = Portfolio.objects.create(owner=self.user, title="V")
        self.assertEqual(available_items(portfolio), {"experience": [], "education": [], "projects": [], "skills": []})

    def test_rows_for_unknown_sections_are_ignored(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="A")
        skill = Skill.objects.create(profile=profile, name="Python")
        portfolio = Portfolio.objects.create(owner=self.user, title="V")
        PortfolioContentSetup.objects.create(portfolio=portfolio)
        PortfolioContentSelection.objects.create(portfolio=portfolio, section="skills", item_id=skill.pk)
        PortfolioContentSelection.objects.create(portfolio=portfolio, section="retired-section", item_id=skill.pk)
        self.assertEqual(get_selected_ids(portfolio)["skills"], {skill.pk})
        versions = dna_sources.portfolio_versions(profile)
        self.assertEqual(versions[0].selected["skills"], frozenset({skill.pk}))


class DnaSourceEdgeTests(_Owner):
    def setUp(self):
        super().setUp()
        self.profile = MainProfile.objects.create(owner=self.user, full_name="A", label="Main")

    def test_urls_fall_back_to_the_profile_page(self):
        profile_url = reverse("profiles:view", args=[self.profile.pk])
        self.assertEqual(dna_sources.section_add_url(self.profile, "retired"), profile_url)
        self.assertEqual(dna_sources.item_edit_url(self.profile, "retired", 9), profile_url)
        self.assertEqual(dna_sources._url("nope:missing", 1, "/fallback/"), "/fallback/")
        self.assertEqual(
            dna_sources.section_add_url(self.profile, "skills"),
            reverse("profiles:skills_experience", args=[self.profile.pk]),
        )

    def test_portfolios_of_another_profile_are_left_out(self):
        other = MainProfile.objects.create(owner=self.user, full_name="B", label="Design")
        Portfolio.objects.create(owner=self.user, title="Mine", profile=self.profile)
        Portfolio.objects.create(owner=self.user, title="Theirs", profile=other)
        self.assertEqual([v.name for v in dna_sources.portfolio_versions(self.profile)], ["Mine"])
