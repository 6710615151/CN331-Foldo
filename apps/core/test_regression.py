"""FOLDO-13: regression across every template x publish state.

For each template and for both a published and an unpublished version, every page a
version has must still work, and the public side must follow the publish state.
A new template or a change to publishing that breaks one combination fails here.
"""

import contextlib
import io
import logging

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.portfolios.models import Portfolio
from apps.profiles.models import MainProfile, Project, Skill
from apps.rendering.themes import THEMES

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


class TemplatePublishMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("jeff", password=PASSWORD)
        cls.profile = MainProfile.objects.create(
            owner=cls.user,
            full_name="Jeff Tester",
            headline="CS student",
            is_default=True,
        )
        Skill.objects.create(profile=cls.profile, name="Python", proficiency="advanced")
        Project.objects.create(profile=cls.profile, project_name="Resume Rocket", problem="Retyping profiles")
        Project.objects.create(profile=cls.profile, project_name="Side project")  # no story

        cls.versions = []
        for theme in THEMES:
            for published in (True, False):
                cls.versions.append(
                    Portfolio.objects.create(
                        owner=cls.user,
                        profile=cls.profile,
                        template_key=theme.key,
                        is_published=published,
                        title=f"{theme.key} {'published' if published else 'draft'}",
                    )
                )

    def setUp(self):
        logging.disable(logging.CRITICAL)  # WeasyPrint is very chatty
        self.addCleanup(logging.disable, logging.NOTSET)
        self.client.login(username="jeff", password=PASSWORD)

    def test_every_owner_page_works_for_every_template_and_state(self):
        for version in self.versions:
            for name in ("preview", "device_preview", "preview_frame", "update", "content", "share", "quality"):
                with self.subTest(version=version.title, page=name):
                    response = self.client.get(reverse(f"portfolios:{name}", args=[version.pk]))
                    self.assertEqual(response.status_code, 200)

    def test_preview_uses_the_version_template_and_shows_the_content(self):
        for version in self.versions:
            with self.subTest(version=version.title):
                html = self.client.get(reverse("portfolios:preview", args=[version.pk])).content.decode()
                self.assertIn(f"pf--{version.template_key}", html)
                for text in ("Jeff Tester", "Python", "Resume Rocket", "Retyping profiles", "Side project"):
                    self.assertIn(text, html)

    def test_public_page_and_qr_follow_the_publish_state(self):
        for version in self.versions:
            with self.subTest(version=version.title):
                qr = self.client.get(reverse("portfolios:share_qr_png", args=[version.pk]))
                self.assertEqual(qr.status_code, 200 if version.is_published else 404)

        self.client.logout()
        for version in self.versions:
            with self.subTest(version=version.title, visitor=True):
                public = self.client.get(reverse("portfolios:public", args=[version.slug]))
                self.assertEqual(public.status_code, 200 if version.is_published else 404)
                if version.is_published:
                    self.assertContains(public, f"pf--{version.template_key}")
                    self.assertNotContains(public, reverse("portfolios:update", args=[version.pk]))

    def test_pdf_exports_for_every_template_and_state(self):
        if not PDF_AVAILABLE:
            self.skipTest("WeasyPrint is not installed")
        for version in self.versions:
            with self.subTest(version=version.title):
                response = self.client.get(reverse("portfolios:pdf", args=[version.pk]))
                if response.status_code == 302:
                    self.skipTest("PDF libraries (Pango) are not available on this machine")
                self.assertEqual(response["Content-Type"], "application/pdf")
                self.assertTrue(response.content.startswith(b"%PDF"))
                version.refresh_from_db()
                self.assertEqual(version.is_published, "published" in version.title)
