"""Tests for the ``core`` app: landing page and health-check endpoint."""

import json
import re
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse



class LandingViewTests(TestCase):
    """The public landing / dashboard shell must render correctly."""

    def test_landing_page_returns_200(self):
        response = self.client.get(reverse("core:landing"))
        self.assertEqual(response.status_code, 200)

    def test_landing_page_uses_expected_template(self):
        response = self.client.get(reverse("core:landing"))
        self.assertTemplateUsed(response, "core/landing.html")
        self.assertTemplateUsed(response, "base.html")

    def test_landing_page_shows_product_identity(self):
        response = self.client.get(reverse("core:landing"))
        self.assertContains(response, "FOLDO")
        self.assertContains(response, "One Profile.")
        self.assertContains(response, "Many Forms.")
        self.assertContains(response, "เก็บทุกผลงานไว้ที่เดียว")

    def test_landing_page_is_a_single_hero_screen(self):
        html = self.client.get(reverse("core:landing")).content.decode()
        main = html[html.index("<main"):html.index("</main>")]
        self.assertEqual(len(re.findall(r"^<section", main, flags=re.MULTILINE)), 1)
        self.assertIn('id="hero-heading"', main)

    def test_get_started_sits_under_the_hero_text_as_coming_soon(self):
        """One CTA after the supporting line; inert until the app exists."""
        html = self.client.get(reverse("core:landing")).content.decode()
        main = html[html.index("<main"):html.index("</main>")]
        self.assertEqual(main.count('class="btn'), 1)
        lead = main.index("เก็บทุกผลงานไว้ที่เดียว")
        cta = main.index("Get Started")
        self.assertLess(lead, cta)
        button = main[main.rindex("<button", 0, cta):main.index("</button>", cta)]
        self.assertIn(" disabled", button)
        self.assertIn("เร็วๆ นี้", button)

    def test_landing_page_has_no_placeholder_links(self):
        """Every link must lead somewhere real — no bare "#" stand-ins."""
        response = self.client.get(reverse("core:landing"))
        self.assertNotContains(response, 'href="#"')

    def test_landing_page_is_full_bleed_without_navbar_or_footer(self):
        """The hero carries its own large logo; other pages keep the shell."""
        landing = self.client.get(reverse("core:landing")).content.decode()
        self.assertNotIn("<header", landing)
        self.assertNotIn("<footer", landing)
        self.assertIn("foldo-hero__logo", landing)
        other = self.client.get("/no-such-page/").content.decode()  # custom 404
        self.assertIn("<header", other)
        self.assertIn("<footer", other)

    def test_hero_graphic_is_a_placeholder_behind_the_text(self):
        """The designer's graphic slot comes first in the markup (behind the copy)."""
        html = self.client.get(reverse("core:landing")).content.decode()
        main = html[html.index("<main"):html.index("</main>")]
        self.assertIn('data-asset="Hero illustration', main)
        self.assertLess(main.index("foldo-hero__placeholder"), main.index('id="hero-heading"'))
        self.assertNotIn("<img", main)


class OnboardingViewTests(TestCase):
    """The first-time entry flow must render its three mock steps."""

    def test_onboarding_page_returns_200(self):
        response = self.client.get(reverse("core:onboarding"))
        self.assertEqual(response.status_code, 200)

    def test_onboarding_page_uses_expected_template(self):
        response = self.client.get(reverse("core:onboarding"))
        self.assertTemplateUsed(response, "core/onboarding.html")
        self.assertTemplateUsed(response, "base.html")

    def test_onboarding_page_shows_all_mock_steps(self):
        response = self.client.get(reverse("core:onboarding"))
        for step in response.context["steps"]:
            self.assertContains(response, step["title_en"])
        self.assertEqual(len(response.context["steps"]), 3)

    def test_onboarding_cta_leads_to_dashboard(self):
        response = self.client.get(reverse("core:onboarding"))
        self.assertContains(response, reverse("core:dashboard"))

    def test_onboarding_page_has_no_placeholder_links(self):
        response = self.client.get(reverse("core:onboarding"))
        self.assertNotContains(response, 'href="#"')

    def test_onboarding_page_keeps_the_shared_shell(self):
        html = self.client.get(reverse("core:onboarding")).content.decode()
        self.assertIn("<header", html)
        self.assertIn("<footer", html)


class DashboardViewTests(TestCase):
    """The signed-in app shell must render a sensible empty state."""

    def test_dashboard_page_returns_200(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_page_uses_expected_template(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertTemplateUsed(response, "core/dashboard.html")
        self.assertTemplateUsed(response, "base.html")

    def test_dashboard_shows_empty_profile_state_with_onboarding_link(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertFalse(response.context["summary"]["has_profile"])
        self.assertContains(response, reverse("core:onboarding"))

    def test_dashboard_shows_empty_portfolio_state(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.context["summary"]["portfolios"], [])

    def test_dashboard_page_has_no_placeholder_links(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(response, 'href="#"')

    def test_dashboard_link_is_in_the_shared_navigation(self):
        html = self.client.get(reverse("core:dashboard")).content.decode()
        nav = html[html.index("<header"):html.index("</header>")]
        self.assertIn(reverse("core:dashboard"), nav)
        self.assertIn('aria-current="page"', nav)


class HealthCheckViewTests(TestCase):
    """The health endpoint must be machine-readable and leak nothing."""

    def test_health_check_returns_ok(self):
        response = self.client.get(reverse("core:health"))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "foldo")
        self.assertTrue(payload["checks"]["database"])

    def test_health_check_reports_version_from_settings(self):
        response = self.client.get(reverse("core:health"))
        payload = json.loads(response.content)
        self.assertEqual(payload["version"], settings.FOLDO_VERSION)

    def test_health_check_returns_503_when_a_check_fails(self):
        with mock.patch(
            "apps.core.selectors.DatabaseHealthCheck.is_healthy", return_value=False
        ):
            response = self.client.get(reverse("core:health"))
        self.assertEqual(response.status_code, 503)
        payload = json.loads(response.content)
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["checks"]["database"])

    def test_health_check_exposes_no_secrets(self):
        response = self.client.get(reverse("core:health"))
        body = response.content.decode()
        self.assertNotIn(settings.SECRET_KEY, body)
        # Environment variable names must never appear in the payload.
        for forbidden in ("DJANGO_SECRET_KEY", "DB_PASSWORD", "REDIS_URL"):
            self.assertNotIn(forbidden, body)


class ErrorHandlerTests(TestCase):
    """Custom 404/500 handlers should render friendly pages in production."""

    @override_settings(DEBUG=False)
    def test_custom_404_page_is_used(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "404", status_code=404)
