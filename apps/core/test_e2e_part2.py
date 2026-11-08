"""FOLDO-13 part 2: what happens after a version is published.

Share link / QR (FOLDO-17) -> PDF export (FOLDO-11) -> Portfolio DNA (FOLDO-14) -> Quality Check (FOLDO-16).
Part 1 (test_e2e.py) covers sign-up -> profile -> versions -> content selection -> preview -> publish.
Still to add when FOLDO-09 lands: edits after publishing only reach the public page after a republish.
"""
import contextlib
import io
import logging
import unittest
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

import apps.portfolios.pdf as pdf_module
from apps.portfolios.models import Portfolio
from apps.portfolios.share_kit.services import qr_file
from apps.profiles.models import MainProfile, Project

User = get_user_model()

PASSWORD = "Str0ng-pass!23"


def _pdf_libraries_available():
    """True only if WeasyPrint *and* its system libraries (Pango) load. Quiet: WeasyPrint prints a banner on failure."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


PDF_AVAILABLE = _pdf_libraries_available()


def quiet_pdf_logs(test):
    """WeasyPrint logs hundreds of font/CSS lines per PDF. Hide log output for this test only."""
    logging.disable(logging.CRITICAL)
    test.addCleanup(logging.disable, logging.NOTSET)


class EndToEndPart2Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("jeff", password=PASSWORD)
        cls.profile = MainProfile.objects.create(owner=cls.user, full_name="Jeff Tester", is_default=True)
        cls.story = Project.objects.create(
            profile=cls.profile, project_name="Resume Rocket", problem="Students retype the same profile",
        )
        cls.side = Project.objects.create(profile=cls.profile, project_name="Side project")
        cls.published = Portfolio.objects.create(owner=cls.user, title="Backend jobs", profile=cls.profile)
        cls.draft = Portfolio.objects.create(owner=cls.user, title="Design jobs", profile=cls.profile)

    def setUp(self):
        quiet_pdf_logs(self)
        self.client.login(username="jeff", password=PASSWORD)
        # Choose content and publish through the real pages, as in part 1.
        self.client.post(reverse("portfolios:content", args=[self.published.pk]), {"projects": [self.story.pk]})
        self.client.post(reverse("portfolios:update", args=[self.published.pk]), {
            "title": "Backend jobs", "profile": self.profile.pk, "template_key": "classic", "is_published": "on",
        })
        self.published.refresh_from_db()
        self.public_url = "http://testserver" + reverse("portfolios:public", args=[self.published.slug])

    # --- Share Kit / QR (FOLDO-17) ---

    def test_share_link_and_qr_open_the_published_portfolio(self):
        page = self.client.get(reverse("portfolios:share", args=[self.published.pk]))
        self.assertContains(page, self.public_url)

        # The QR code encodes exactly the public link (same image as a QR made from that URL).
        png = self.client.get(reverse("portfolios:share_qr_png", args=[self.published.pk]))
        self.assertEqual(png["Content-Type"], "image/png")
        self.assertEqual(png.content, qr_file(self.public_url, "png"))

        # Someone who scans it, without an account, sees the selected content only.
        self.client.logout()
        public = self.client.get(self.public_url)
        self.assertContains(public, "Resume Rocket")
        self.assertNotContains(public, "Side project")

    def test_unpublished_version_has_no_link_and_no_qr(self):
        page = self.client.get(reverse("portfolios:share", args=[self.draft.pk]))
        self.assertContains(page, "ยังไม่เผยแพร่")
        self.assertEqual(self.client.get(reverse("portfolios:share_qr_png", args=[self.draft.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("portfolios:share_qr_svg", args=[self.draft.pk])).status_code, 404)

        # Unpublishing takes the link and the QR away again.
        self.client.post(reverse("portfolios:update", args=[self.published.pk]), {
            "title": "Backend jobs", "profile": self.profile.pk, "template_key": "classic",
        })
        self.assertEqual(self.client.get(reverse("portfolios:share_qr_png", args=[self.published.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.public_url).status_code, 404)

    # --- PDF export (FOLDO-11) ---

    @unittest.skipUnless(PDF_AVAILABLE, "WeasyPrint is not installed")
    def test_pdf_has_the_selected_content_and_does_not_publish(self):
        self.client.post(reverse("portfolios:content", args=[self.draft.pk]), {"projects": [self.side.pk]})

        captured = {}
        real_render = pdf_module.render_version_html

        def spy(*args, **kwargs):
            captured["html"] = real_render(*args, **kwargs)
            captured["kwargs"] = kwargs
            return captured["html"]

        with mock.patch.object(pdf_module, "render_version_html", side_effect=spy):
            response = self.client.get(reverse("portfolios:pdf", args=[self.draft.pk]))
        if response.status_code == 302:
            self.skipTest("PDF libraries (Pango) are not available on this machine")

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        # Built from the version's own selection, without the owner toolbar.
        self.assertIn("Side project", captured["html"])
        self.assertNotIn("Resume Rocket", captured["html"])
        self.assertIs(captured["kwargs"].get("toolbar"), False)
        # Exporting a draft never publishes it.
        self.draft.refresh_from_db()
        self.assertFalse(self.draft.is_published)

    @unittest.skipUnless(PDF_AVAILABLE, "WeasyPrint is not installed")
    def test_pdf_of_long_content_runs_over_several_pages(self):
        try:
            from weasyprint import CSS, HTML, default_url_fetcher
        except OSError:
            self.skipTest("PDF libraries (Pango) are not available on this machine")

        self.profile.bio = "A long paragraph about my work. " * 400
        self.profile.save()
        html = pdf_module.render_version_html(self.published, request=None, preview=False, toolbar=False)
        document = HTML(
            string=html, base_url=pdf_module.BASE_URL,
            url_fetcher=pdf_module._make_fetcher(default_url_fetcher),
        ).render(stylesheets=[CSS(string=pdf_module.PRINT_CSS)])
        self.assertGreater(len(document.pages), 1)

    # --- Portfolio DNA (FOLDO-14) ---

    def test_dna_shows_which_versions_use_each_project(self):
        page = self.client.get(reverse("insights:dna", args=[self.profile.pk]))
        self.assertEqual(page.status_code, 200)
        used_by = {row.item.title: {v.name for v in row.used_in} for row in page.context["dna"].rows}
        # "Backend jobs" chose one project; "Design jobs" was never customised, so it shows both.
        self.assertEqual(used_by["Resume Rocket"], {"Backend jobs", "Design jobs"})
        self.assertEqual(used_by["Side project"], {"Design jobs"})

    # --- Quality Check (FOLDO-16) ---

    def test_quality_check_reports_without_changing_anything(self):
        before = (Portfolio.objects.get(pk=self.published.pk).updated_at, Project.objects.count())
        self.assertEqual(self.client.get(reverse("portfolios:quality", args=[self.published.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("portfolios:quality", args=[self.published.pk])).status_code, 405)
        after = (Portfolio.objects.get(pk=self.published.pk).updated_at, Project.objects.count())
        self.assertEqual(before, after)

    # --- Privacy across the new pages ---

    def test_another_user_cannot_reach_share_pdf_dna_or_quality(self):
        User.objects.create_user("stranger", password=PASSWORD)
        self.client.logout()
        self.client.login(username="stranger", password=PASSWORD)
        for url in (
            reverse("portfolios:share", args=[self.published.pk]),
            reverse("portfolios:share_qr_png", args=[self.published.pk]),
            reverse("portfolios:pdf", args=[self.published.pk]),
            reverse("insights:dna", args=[self.profile.pk]),
            reverse("portfolios:quality", args=[self.published.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
