"""FOLDO-08: device preview (desktop / mobile), loading and rendering-error states."""
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.profiles.models import MainProfile

from .models import Portfolio

User = get_user_model()


class DevicePreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="pass-12345")
        cls.bob = User.objects.create_user("bob", password="pass-12345")
        MainProfile.objects.create(owner=cls.alice, full_name="Alice Doe", is_default=True)
        cls.portfolio = Portfolio.objects.create(owner=cls.alice, title="Alice for internships")
        cls.device_url = reverse("portfolios:device_preview", args=[cls.portfolio.pk])
        cls.frame_url = reverse("portfolios:preview_frame", args=[cls.portfolio.pk])

    def setUp(self):
        self.client.login(username="alice", password="pass-12345")

    # --- desktop / mobile modes ---

    def test_desktop_is_the_default_mode(self):
        response = self.client.get(self.device_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["mode"], "desktop")
        self.assertContains(response, "foldo-device--desktop")

    def test_mobile_mode(self):
        response = self.client.get(self.device_url, {"mode": "mobile"})
        self.assertEqual(response.context["mode"], "mobile")
        self.assertContains(response, "foldo-device--mobile")

    def test_unknown_mode_falls_back_to_desktop(self):
        response = self.client.get(self.device_url, {"mode": "<script>"})
        self.assertEqual(response.context["mode"], "desktop")
        self.assertNotContains(response, "foldo-device--<script>")

    def test_switch_links_and_current_mode_marked(self):
        response = self.client.get(self.device_url, {"mode": "mobile"})
        self.assertContains(response, 'href="?mode=desktop"')
        self.assertContains(response, 'href="?mode=mobile" aria-current="true"')

    def test_page_loads_the_frame_and_links_back_to_edit(self):
        response = self.client.get(self.device_url)
        self.assertContains(response, f'src="{self.frame_url}"')
        self.assertContains(response, reverse("portfolios:update", args=[self.portfolio.pk]))
        self.assertContains(response, reverse("portfolios:list"))

    def test_loading_state_is_shown_until_the_frame_loads(self):
        response = self.client.get(self.device_url)
        self.assertContains(response, "data-preview-loading")
        self.assertContains(response, "Loading preview")

    def test_list_page_links_to_device_preview(self):
        response = self.client.get(reverse("portfolios:list"))
        self.assertContains(response, self.device_url)

    # --- the frame ---

    def test_frame_shows_the_portfolio_without_the_preview_bar(self):
        response = self.client.get(self.frame_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Doe")
        self.assertNotContains(response, "All portfolios")

    def test_frame_may_be_embedded_by_this_site_only(self):
        response = self.client.get(self.frame_url)
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(response["X-Robots-Tag"], "noindex")

    def test_preview_does_not_publish(self):
        self.client.get(self.device_url)
        self.client.get(self.frame_url)
        self.portfolio.refresh_from_db()
        self.assertFalse(self.portfolio.is_published)

    # --- rendering-error state ---

    def test_rendering_error_shows_a_message_not_a_crash(self):
        with mock.patch("apps.portfolios.views._render_portfolio", side_effect=RuntimeError("boom")):
            with self.assertLogs("apps.portfolios.views", level="ERROR"), self.assertLogs("django.request", level="ERROR"):
                response = self.client.get(self.frame_url)
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "couldn't show this preview", status_code=500)
        self.assertContains(response, reverse("portfolios:update", args=[self.portfolio.pk]), status_code=500)
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")

    # --- privacy ---

    def test_other_users_get_404(self):
        self.client.logout()
        self.client.login(username="bob", password="pass-12345")
        self.assertEqual(self.client.get(self.device_url).status_code, 404)
        self.assertEqual(self.client.get(self.frame_url).status_code, 404)

    def test_signed_out_users_go_to_login(self):
        self.client.logout()
        for url in (self.device_url, self.frame_url):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse(settings.LOGIN_URL), response["Location"])