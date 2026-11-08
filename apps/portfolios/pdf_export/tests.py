"""Tests for the PDF export workflow and layout (FOLDO-11, Dev 2)."""
import contextlib
import datetime
import io
import logging
import threading
import unittest
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.shortcuts import resolve_url
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.portfolios import pdf as pdf_module
from apps.portfolios.models import Portfolio
from apps.portfolios.services import render_version_html
from apps.profiles.models import Experience, MainProfile, Project, Skill

PASSWORD = "s3cret-pass"
LONG_SENTENCE = "Built and maintained a large Django application with many moving parts. "
RENDER_TIME_LIMIT = 120  # seconds; the nested-grid bug made this run for minutes


def _pdf_libraries_available():
    """True only if WeasyPrint and its system libraries (Pango) load."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def _pypdf():
    try:
        import pypdf
    except ImportError:
        return None
    return pypdf


PDF_AVAILABLE = _pdf_libraries_available()
PYPDF = _pypdf()


class ExportTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", email="a@example.com", password=PASSWORD)
        self.bob = User.objects.create_user(username="bob", email="b@example.com", password=PASSWORD)
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice A")
        self.draft = Portfolio.objects.create(owner=self.alice, title="Draft", profile=self.profile)
        self.bob_portfolio = Portfolio.objects.create(owner=self.bob, title="Bob Folio")
        self.client.force_login(self.alice)

    def export_url(self, portfolio=None):
        return reverse("portfolios:export", args=[(portfolio or self.draft).pk])

    def pdf_url(self, portfolio=None, **query):
        url = reverse("portfolios:pdf", args=[(portfolio or self.draft).pk])
        return url + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else "")

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class ExportPageTests(ExportTestCase):
    def test_owner_sees_the_page(self):
        self.assertEqual(self.client.get(self.export_url()).status_code, 200)

    def test_other_users_portfolio_is_404(self):
        self.assertEqual(self.client.get(self.export_url(self.bob_portfolio)).status_code, 404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(self.export_url())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(resolve_url(settings.LOGIN_URL)))

    def test_page_offers_both_page_sizes_with_a4_selected(self):
        html = self.client.get(self.export_url()).content.decode()
        self.assertIn('value="A4" checked', html)
        self.assertIn('value="Letter"', html)

    def test_form_is_a_plain_download_link_so_it_works_without_javascript(self):
        html = self.client.get(self.export_url()).content.decode()
        self.assertIn(f'method="get" action="{self.pdf_url()}"', html)

    def test_page_has_a_panel_for_every_state_and_a_retry_button(self):
        html = self.client.get(self.export_url()).content.decode()
        for state in ("progress", "success", "failure"):
            self.assertIn(f'data-state-panel="{state}"', html)
        self.assertIn("data-export-retry", html)
        self.assertIn("data-export-cancel", html)
        self.assertIn("ดาวน์โหลด PDF", html)

    def test_state_panels_start_hidden(self):
        html = self.client.get(self.export_url()).content.decode()
        for state in ("progress", "success", "failure"):
            panel = html.split(f'data-state-panel="{state}"')[1].split(">")[0]
            self.assertIn("hidden", panel)

    def test_page_says_exporting_does_not_publish_and_never_does(self):
        html = self.client.get(self.export_url()).content.decode()
        self.assertIn("ไม่ได้เผยแพร่พอร์ตโฟลิโอ", html)
        self.draft.refresh_from_db()
        self.assertFalse(self.draft.is_published)

    def test_list_page_links_to_the_export_page(self):
        html = self.client.get(reverse("portfolios:list")).content.decode()
        self.assertIn(self.export_url(), html)

    def test_pages_are_not_cached(self):
        self.assertIn("no-store", self.client.get(self.export_url())["Cache-Control"])


class PdfEndpointTests(ExportTestCase):
    """The workflow around render_pdf: sizes, and honest failure reporting."""

    def test_page_size_is_passed_on(self):
        with mock.patch("apps.portfolios.views.render_pdf", return_value=b"%PDF-1.7 x") as render:
            response = self.client.get(self.pdf_url(size="Letter"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(render.call_args.kwargs["page_size"], "Letter")

    def test_unknown_page_size_falls_back_to_a4(self):
        with mock.patch("apps.portfolios.views.render_pdf", return_value=b"%PDF-1.7 x") as render:
            self.client.get(self.pdf_url(size="Tabloid"))
        self.assertEqual(render.call_args.kwargs["page_size"], "A4")

    def test_success_is_an_attachment_pdf(self):
        with mock.patch("apps.portfolios.views.render_pdf", return_value=b"%PDF-1.7 x"):
            response = self.client.get(self.pdf_url())
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_failure_in_page_is_a_json_error_not_a_success(self):
        with mock.patch("apps.portfolios.views.render_pdf", side_effect=RuntimeError("boom")):
            response = self.client.get(self.pdf_url(), HTTP_X_FOLDO_EXPORT="1")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("ลองอีกครั้ง", response.json()["error"])

    def test_missing_pdf_libraries_in_page_is_503(self):
        with mock.patch("apps.portfolios.views.render_pdf", side_effect=pdf_module.PdfUnavailable("no pango")):
            response = self.client.get(self.pdf_url(), HTTP_X_FOLDO_EXPORT="1")
        self.assertEqual(response.status_code, 503)
        self.assertIn("ยังสร้าง PDF ไม่ได้", response.json()["error"])

    def test_failure_without_javascript_redirects_with_a_message(self):
        with mock.patch("apps.portfolios.views.render_pdf", side_effect=RuntimeError("boom")):
            response = self.client.get(self.pdf_url())
        self.assertRedirects(response, reverse("portfolios:list"), fetch_redirect_response=False)
        self.assertIn("สร้าง PDF ไม่สำเร็จ ลองอีกครั้ง", self.messages(response))

    def test_other_users_cannot_export(self):
        for header in ({}, {"HTTP_X_FOLDO_EXPORT": "1"}):
            response = self.client.get(self.pdf_url(self.bob_portfolio), **header)
            self.assertEqual(response.status_code, 404)

    def test_exporting_does_not_publish(self):
        with mock.patch("apps.portfolios.views.render_pdf", return_value=b"%PDF-1.7 x"):
            self.client.get(self.pdf_url())
        self.draft.refresh_from_db()
        self.assertFalse(self.draft.is_published)

    def test_a_renderer_that_returns_no_pdf_is_an_error(self):
        """render_pdf itself refuses to call non-PDF output a success."""
        fake_weasyprint = mock.MagicMock()
        fake_weasyprint.HTML.return_value.write_pdf.return_value = b"<html>not a pdf</html>"
        with mock.patch.dict("sys.modules", {"weasyprint": fake_weasyprint}):
            with self.assertRaises(RuntimeError):
                pdf_module.render_pdf(self.draft, request=None)


class PrintCssTests(TestCase):
    def test_sizes(self):
        self.assertIn("size: A4", pdf_module.print_css("A4"))
        self.assertIn("size: Letter", pdf_module.print_css("Letter"))

    def test_unknown_size_is_not_injected_into_the_css(self):
        css = pdf_module.print_css("A4; } body { display: none")
        self.assertNotIn("display: none", css)
        self.assertIn("size: A4", css)

    def test_old_constant_is_still_there(self):
        self.assertIn("size: A4", pdf_module.PRINT_CSS)


def heavy_profile(owner):
    """A long portfolio: several pages of text, story fields, many skills, an unbroken URL."""
    profile = MainProfile.objects.create(owner=owner, label="Heavy", full_name="Heavy Hitter", bio=LONG_SENTENCE * 20)
    for i in range(1, 7):
        Experience.objects.create(
            profile=profile, company=f"Company {i}", job_title=f"Engineer {i}",
            start_date=datetime.date(2010 + i, 1, 1), end_date=datetime.date(2011 + i, 1, 1),
            description=LONG_SENTENCE * 10 + f"ENDMARK-EXP-{i}",
        )
    for i in range(1, 5):
        Project.objects.create(
            profile=profile, project_name=f"Project {i}", description=LONG_SENTENCE * 6,
            project_url="https://example.com/" + "very-long-path-" * 10 + "end",
            problem=LONG_SENTENCE * 6, role="Team lead", process=LONG_SENTENCE * 6,
            solution=LONG_SENTENCE * 6, outcome=f"ENDMARK-PRJ-{i}",
        )
    for i in range(1, 31):
        Skill.objects.create(profile=profile, name=f"Skill {i}", proficiency="advanced")
    return profile


def run_with_limit(function, seconds):
    """Run ``function`` in a thread; fail instead of hanging the test run if it never ends."""
    box = {}

    def target():
        try:
            box["value"] = function()
        except BaseException as exc:  # noqa: BLE001 - reported below
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise AssertionError(f"PDF rendering did not finish within {seconds}s")
    if "error" in box:
        raise box["error"]
    return box["value"]


@unittest.skipUnless(PDF_AVAILABLE, "WeasyPrint or its system libraries (Pango) are not installed")
class RealPdfTests(ExportTestCase):
    """Real PDFs: they paginate, keep every piece of text, and finish in reasonable time."""

    def setUp(self):
        super().setUp()
        logging.disable(logging.CRITICAL)  # WeasyPrint logs hundreds of font lines per PDF
        self.addCleanup(logging.disable, logging.NOTSET)
        self.heavy = heavy_profile(self.alice)

    def pdf_for(self, template_key, page_size="A4"):
        portfolio = Portfolio.objects.create(
            owner=self.alice, title=f"Heavy {template_key}", profile=self.heavy, template_key=template_key
        )
        request = RequestFactory().get("/", HTTP_HOST="testserver")
        request.user = self.alice
        # The database is read here, in the test's own thread; only WeasyPrint (which needs no
        # database) runs under the time limit.
        html = render_version_html(portfolio, request=request, preview=False, toolbar=False)
        from weasyprint import CSS, HTML, default_url_fetcher

        def write():
            document = HTML(string=html, base_url=pdf_module.BASE_URL,
                            url_fetcher=pdf_module._make_fetcher(default_url_fetcher))
            return document.write_pdf(stylesheets=[CSS(string=pdf_module.print_css(page_size))])

        return run_with_limit(write, RENDER_TIME_LIMIT)

    def read(self, data):
        self.assertIsNotNone(PYPDF, "pypdf is needed to read the PDF back")
        return PYPDF.PdfReader(io.BytesIO(data))

    @unittest.skipIf(PYPDF is None, "pypdf is not installed")
    def test_every_template_paginates_and_keeps_all_text(self):
        for key in ("classic", "modern", "creative"):
            with self.subTest(template=key):
                reader = self.read(self.pdf_for(key))
                self.assertGreater(len(reader.pages), 3)
                # Compared without whitespace: a line may break right after a hyphen.
                text = "".join("".join(page.extract_text() or "" for page in reader.pages).split())
                # The end of every long description made it onto a page: nothing was clipped.
                for i in range(1, 7):
                    self.assertIn(f"ENDMARK-EXP-{i}", text)
                for i in range(1, 5):
                    self.assertIn(f"ENDMARK-PRJ-{i}", text)
                for name in ("Skill1", "Skill30", "Company6", "Project4"):
                    self.assertIn(name, text)

    @unittest.skipIf(PYPDF is None, "pypdf is not installed")
    def test_page_sizes(self):
        a4 = self.read(self.pdf_for("classic", "A4")).pages[0].mediabox
        letter = self.read(self.pdf_for("classic", "Letter")).pages[0].mediabox
        self.assertAlmostEqual(float(a4.width), 595.3, delta=1)
        self.assertAlmostEqual(float(a4.height), 841.9, delta=1)
        self.assertAlmostEqual(float(letter.width), 612, delta=1)
        self.assertAlmostEqual(float(letter.height), 792, delta=1)

    @unittest.skipIf(PYPDF is None, "pypdf is not installed")
    def test_long_unbroken_name_does_not_lose_text(self):
        self.heavy.full_name = "Name" + "verylongunbrokenword" * 5
        self.heavy.save()
        text = "".join(page.extract_text() or "" for page in self.read(self.pdf_for("classic")).pages)
        self.assertIn("verylongunbrokenword", text)

    def test_export_through_the_real_view_returns_a_pdf(self):
        portfolio = Portfolio.objects.create(owner=self.alice, title="Heavy view", profile=self.heavy)
        response = self.client.get(self.pdf_url(portfolio, size="Letter"), HTTP_X_FOLDO_EXPORT="1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
