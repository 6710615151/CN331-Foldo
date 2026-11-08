"""Tests for the Share Kit: copy link and QR code (FOLDO-17)."""
import re

import segno
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from apps.profiles.models import MainProfile, Skill

from ..models import Portfolio
from . import services

PASSWORD = "s3cret-pass"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ShareKitTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", email="a@example.com", password=PASSWORD)
        self.bob = User.objects.create_user(username="bob", email="b@example.com", password=PASSWORD)
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice A")
        Skill.objects.create(profile=self.profile, name="PythonSkillX")
        self.draft = Portfolio.objects.create(owner=self.alice, title="Draft", profile=self.profile)
        self.live = Portfolio.objects.create(owner=self.alice, title="Live", profile=self.profile, is_published=True)
        self.bob_live = Portfolio.objects.create(owner=self.bob, title="Bob Live", is_published=True)
        self.client.force_login(self.alice)

    def share(self, portfolio):
        return self.client.get(reverse("portfolios:share", args=[portfolio.pk]))

    def qr(self, portfolio, fmt="png"):
        return self.client.get(reverse(f"portfolios:share_qr_{fmt}", args=[portfolio.pk]))

    def expected_url(self, portfolio):
        return "http://testserver" + reverse("portfolios:public", args=[portfolio.slug])


class PrivacyTests(ShareKitTestCase):
    def pages(self, portfolio):
        return {
            "page": reverse("portfolios:share", args=[portfolio.pk]),
            "png": reverse("portfolios:share_qr_png", args=[portfolio.pk]),
            "svg": reverse("portfolios:share_qr_svg", args=[portfolio.pk]),
        }

    def test_owner_gets_every_page_of_a_published_version(self):
        for name, url in self.pages(self.live).items():
            with self.subTest(name):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_other_user_gets_404_even_for_a_published_version(self):
        for name, url in self.pages(self.bob_live).items():
            with self.subTest(name):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        for name, url in self.pages(self.live).items():
            with self.subTest(name):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(resolve_url(settings.LOGIN_URL)))

    def test_pages_are_read_only(self):
        self.client.post(reverse("portfolios:share", args=[self.draft.pk]))
        self.draft.refresh_from_db()
        self.assertFalse(self.draft.is_published)


class PublishedTests(ShareKitTestCase):
    def test_page_shows_status_url_and_qr(self):
        html = self.share(self.live).content.decode()
        self.assertIn("Published", html)
        self.assertIn(self.expected_url(self.live), html)
        self.assertIn("<svg", html)
        self.assertIn(reverse("portfolios:share_qr_png", args=[self.live.pk]), html)

    def test_inline_qr_is_built_from_the_exact_public_url(self):
        html = self.share(self.live).content.decode()
        expected = services.qr_svg_inline(self.expected_url(self.live), title=f"QR code for {self.live.title}")
        self.assertIn(expected, html)

    def test_inline_qr_scales_instead_of_being_cropped(self):
        """Regression: a fixed width/height with no viewBox cut the code off in a smaller box."""
        svg = services.qr_svg_inline(self.expected_url(self.live), title="t")
        self.assertIn("viewBox=", svg)
        self.assertNotRegex(svg, r'<svg[^>]*\swidth=')
        self.assertNotRegex(svg, r'<svg[^>]*\sheight=')

    def test_png_download_is_a_png_for_the_public_url(self):
        response = self.qr(self.live)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(PNG_MAGIC))
        self.assertIn(f'{self.live.slug}-qr.png', response["Content-Disposition"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response.content, services.qr_file(self.expected_url(self.live), "png"))

    def test_svg_download_matches_the_public_url(self):
        response = self.qr(self.live, "svg")
        self.assertEqual(response["Content-Type"], "image/svg+xml")
        self.assertEqual(response.content, services.qr_file(self.expected_url(self.live), "svg"))

    def test_qr_matrix_encodes_the_url(self):
        url = self.expected_url(self.live)
        # Same text in, same modules out; a different URL gives a different code.
        self.assertEqual(segno.make(url, error="m").matrix, segno.make(url, error="m").matrix)
        self.assertNotEqual(segno.make(url, error="m").matrix, segno.make(url + "x", error="m").matrix)

    def test_the_link_in_the_page_really_opens_the_public_page(self):
        html = self.share(self.live).content.decode()
        url = re.search(r'id="sk-url" value="([^"]+)"', html).group(1)
        self.client.logout()
        response = self.client.get(url.replace("http://testserver", ""))
        self.assertEqual(response.status_code, 200)

    def test_responses_are_not_cached(self):
        self.assertIn("no-store", self.share(self.live)["Cache-Control"])
        self.assertIn("no-store", self.qr(self.live)["Cache-Control"])


class UnpublishedTests(ShareKitTestCase):
    def test_page_says_unpublished_and_shows_no_link_or_qr(self):
        html = self.share(self.draft).content.decode()
        self.assertIn("not published yet", html)
        self.assertNotIn("<svg", html)
        self.assertNotIn("sk-url", html)
        self.assertNotIn(self.draft.slug, html)

    def test_page_points_to_the_edit_screen_to_publish(self):
        html = self.share(self.draft).content.decode()
        self.assertIn(reverse("portfolios:update", args=[self.draft.pk]), html)

    def test_downloads_are_404_while_unpublished(self):
        self.assertEqual(self.qr(self.draft).status_code, 404)
        self.assertEqual(self.qr(self.draft, "svg").status_code, 404)

    def test_the_public_page_is_404_too(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.draft.public_path).status_code, 404)

    def test_unpublishing_removes_the_link_and_qr(self):
        self.assertEqual(self.qr(self.live).status_code, 200)
        self.live.is_published = False
        self.live.save()
        self.assertEqual(self.qr(self.live).status_code, 404)
        self.assertNotIn("<svg", self.share(self.live).content.decode())
        self.client.logout()
        self.assertEqual(self.client.get(self.live.public_path).status_code, 404)

    def test_publishing_turns_the_link_and_qr_on(self):
        self.draft.is_published = True
        self.draft.save()
        self.assertEqual(self.qr(self.draft).status_code, 200)
        self.assertIn(self.expected_url(self.draft), self.share(self.draft).content.decode())


class ServiceTests(ShareKitTestCase):
    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValueError):
            services.qr_file("http://example.com", "gif")

    def test_public_url_uses_the_route_of_the_public_page(self):
        class Request:
            @staticmethod
            def build_absolute_uri(path):
                return "https://foldo.example" + path

        self.assertEqual(
            services.public_url(self.live, Request),
            "https://foldo.example" + reverse("portfolios:public", args=[self.live.slug]),
        )

    def test_list_page_links_to_share(self):
        html = self.client.get(reverse("portfolios:list")).content.decode()
        self.assertIn(reverse("portfolios:share", args=[self.live.pk]), html)
