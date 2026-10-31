"""Tests for the ``core`` app: landing page and health-check endpoint."""

import json
import re
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

# ------------------- FOLDO-10 initial repeatable tests ------------------- 
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory
from django.views.generic import DetailView

from .mixins import OwnerRequiredMixin
# -------------------------------------------------------------------------

# ------------------- FOLDO-10: imports for the shared-validator tests -------------------
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .validators import safe_url_validator
# ------------------------------------------------------------------------


# ------------------- FOLDO-10: imports for the shared form-display tests -------------------
from django import forms
from django.template import Context, Template

from .forms import BootstrapFormMixin
from .validators import MAX_SHORT_NAME
# ------------------------------------------------------------------------

# -------------------FOLDO-10: imports for the 403 page test-------------------
from django.core.exceptions import PermissionDenied
from django.urls import include, path
# ------------------------------------------------------------------------

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
        self.assertEqual(main.count('class="btn'), 2)
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

# ---------------------------------------------------------------------------
# FOLDO-10: data ownership (apps/core/mixins.py)
# ---------------------------------------------------------------------------


class _OwnAccountView(OwnerRequiredMixin, DetailView):
    """Test-only view: show one account, but only to its owner."""

    model = get_user_model()
    owner_field = "pk"
    template_name = "base.html"


class OwnerRequiredMixinTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(username="alice", password="s3cret-pass")
        self.bobby = User.objects.create_user(username="bobby", password="s3cret-pass")
        self.factory = RequestFactory()

    def _open(self, user, pk):
        """Open row `pk` while signed in as `user`."""
        request = self.factory.get("/")
        request.user = user
        return _OwnAccountView.as_view()(request, pk=pk)

    def test_owner_can_open_own_row(self):
        response = self._open(self.alice, self.alice.pk)
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404_not_403(self):
        """IDOR: changing the id in the URL must not show someone else's data."""
        with self.assertRaises(Http404):
            self._open(self.bobby, self.alice.pk)

    def test_not_signed_in_is_redirected_to_login(self):
        response = self._open(AnonymousUser(), self.alice.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)



# ---------------------------------------------------------------------------
# FOLDO-10: shared validators (apps/core/validators.py)
# ---------------------------------------------------------------------------


class SafeUrlValidatorTests(SimpleTestCase):
    def test_accepts_http_and_https_links(self):
        for url in ("http://example.com", "https://github.com/foldo/project"):
            safe_url_validator(url) 

    def test_rejects_links_that_are_not_http_or_https(self):
        for url in ("javascript:alert(1)", "data:text/html,hello", "ftp://example.com/cv.pdf"):
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    safe_url_validator(url)

# ---------------------------------------------------------------------------
# FOLDO-10: shared form display (apps/core/forms.py + templates/partials/form_*.html)
# ---------------------------------------------------------------------------


class _SampleForm(BootstrapFormMixin, forms.Form):
    """Test-only form that uses the shared rules like a real FOLDO form would."""

    name = forms.CharField(label="Name", max_length=MAX_SHORT_NAME)
    website = forms.URLField(
        label="Website", required=False, assume_scheme="https",
        validators=[safe_url_validator],
    )
    agree = forms.BooleanField(label="Agree", required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("name") == "taken":
            raise forms.ValidationError("This name is already used.")
        return cleaned


_FORM_TEMPLATE = Template(
    '{% include "partials/form_errors.html" %}'
    '{% for field in form %}{% include "partials/form_field.html" %}{% endfor %}'
)


class FormDisplayTests(SimpleTestCase):
    def _render(self, data=None):
        form = _SampleForm(data=data)
        if data is not None:
            form.is_valid()
        return _FORM_TEMPLATE.render(Context({"form": form}))

    def test_fields_get_bootstrap_classes(self):
        html = self._render()
        self.assertIn('class="form-control"', html)
        self.assertIn('class="form-check-input"', html)
        self.assertNotIn("is-invalid", html)

    def test_field_error_is_shown_under_the_field(self):
        html = self._render({"name": "", "website": "ftp://example.com"})
        self.assertIn("is-invalid", html)
        self.assertIn('aria-invalid="true"', html)
        self.assertIn('id="id_name_error"', html)  # linked to aria-describedby

    def test_whole_form_error_is_shown_at_the_top(self):
        html = self._render({"name": "taken"})
        self.assertIn('class="alert alert-danger"', html)
        self.assertIn("This name is already used.", html)

    def test_user_input_is_escaped_not_run(self):
        """XSS: text a user typed must come back as text, never as HTML."""
        html = self._render({"name": "<script>alert(1)</script>" * 10})
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

# ---------------------------------------------------------------------------
# FOLDO-10: 403 "access denied" page (templates/403.html)
# ---------------------------------------------------------------------------


def _always_forbidden(request):
    raise PermissionDenied


urlpatterns = [
    path("", include("apps.core.urls")),
    path("forbidden/", _always_forbidden),
]


@override_settings(ROOT_URLCONF="apps.core.tests")
class PermissionDeniedPageTests(TestCase):
    def test_custom_403_page_is_used(self):
        response = self.client.get("/forbidden/")
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "have access to this page", status_code=403)



# ---------------------------------------------------------------------------
# FOLDO-10: empty state (templates/partials/empty_state.html)
# ---------------------------------------------------------------------------


class EmptyStateTests(SimpleTestCase):
    def _render(self, **params):
        template = Template('{% include "partials/empty_state.html" %}')
        return template.render(Context(params))

    def test_shows_message_and_button(self):
        html = self._render(message="No education yet", action_url="/add/", action_label="Add education")
        self.assertIn("No education yet", html)
        self.assertIn('href="/add/"', html)
        self.assertIn("Add education", html)

    def test_button_is_optional(self):
        html = self._render(message="Nothing here yet")
        self.assertIn("Nothing here yet", html)
        self.assertNotIn("<a ", html)

    def test_message_is_escaped(self):
        html = self._render(message="<b>hi</b>")
        self.assertIn("&lt;b&gt;hi&lt;/b&gt;", html)