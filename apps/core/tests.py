"""Tests for the ``core`` app: landing page and health-check endpoint."""

import json
import re
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.shortcuts import resolve_url

# ------------------- FOLDO-10 initial repeatable tests ------------------- 
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory
from django.views.generic import DetailView

from .mixins import OwnerRequiredMixin
from apps.profiles.models import MainProfile
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

# -------------------FOLDO-10: imports for the date-order tests-------------------
from datetime import date

from .validators import validate_date_order
# ------------------------------------------------------------------------


# -------------------FOLDO-15: imports for the project-story display tests-------------------
from types import SimpleNamespace
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
        self.assertContains(response, "เก็บโปรไฟล์ไว้ที่เดียว")

    def test_landing_page_is_a_single_hero_screen(self):
        html = self.client.get(reverse("core:landing")).content.decode()
        main = html[html.index("<main"):html.index("</main>")]
        self.assertEqual(len(re.findall(r"^<section", main, flags=re.MULTILINE)), 1)
        self.assertIn('id="hero-heading"', main)

    def _get_started_link(self):
        html = self.client.get(reverse("core:landing")).content.decode()
        main = html[html.index("<main"):html.index("</main>")]
        cta = main.index("foldo-hero__cta")
        self.assertLess(main.index("เก็บโปรไฟล์ไว้ที่เดียว"), cta)
        return main[main.rindex("<a", 0, cta):main.index("</a>", cta)]

    def test_get_started_sends_new_visitors_to_sign_up(self):
        link = self._get_started_link()
        self.assertIn(reverse("accounts:register"), link)
        self.assertNotIn(" disabled", link)

    def test_get_started_sends_signed_in_users_to_dashboard(self):
        user = get_user_model().objects.create_user(username="dev3", password="pw-Foldo-12345")
        self.client.force_login(user)
        self.assertIn(reverse("core:dashboard"), self._get_started_link())

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

    def test_hero_illustration_sits_behind_the_text(self):
        """The decorative hero image comes first in the markup (behind the copy)."""
        html = self.client.get(reverse("core:landing")).content.decode()
        main = html[html.index("<main"):html.index("</main>")]
        self.assertIn("images/hero-illustration.png", main)
        self.assertLess(main.index("foldo-hero__art"), main.index('id="hero-heading"'))
        art = main[main.rindex("<img", 0, main.index("foldo-hero__art")):]
        self.assertIn('alt=""', art[:art.index(">")])

    def test_hero_logo_uses_the_brand_mark(self):
        html = self.client.get(reverse("core:landing")).content.decode()
        self.assertIn("images/logo-mark.png", html)
        self.assertNotIn("foldo-asset", html[html.index("<main"):html.index("</main>")].replace("foldo-asset-img", ""))


class SignedInTestCase(TestCase):
    """Signs a user in before each test, for pages behind login."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev3", password="pw-Foldo-12345"
        )
        self.client.force_login(self.user)


class OnboardingViewTests(SignedInTestCase):
    """The first-time entry flow renders three steps; step 1 tracks the Main Profile."""

    def test_onboarding_redirects_visitors_to_login(self):
        self.client.logout()
        url = reverse("core:onboarding")
        response = self.client.get(url)
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False
        )

    def test_onboarding_page_returns_200(self):
        response = self.client.get(reverse("core:onboarding"))
        self.assertEqual(response.status_code, 200)

    def test_onboarding_page_uses_expected_template(self):
        response = self.client.get(reverse("core:onboarding"))
        self.assertTemplateUsed(response, "core/onboarding.html")
        self.assertTemplateUsed(response, "base.html")

    def test_onboarding_page_shows_all_steps(self):
        response = self.client.get(reverse("core:onboarding"))
        for step in response.context["steps"]:
            self.assertContains(response, step["title"])
        self.assertEqual(len(response.context["steps"]), 3)

    def test_step_one_links_to_create_when_user_has_no_profile(self):
        step = self.client.get(reverse("core:onboarding")).context["steps"][0]
        self.assertFalse(step["done"])
        self.assertEqual(step["action_url"], reverse("profiles:create"))

    def test_step_one_is_done_once_user_has_a_profile(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="Dev Three")
        response = self.client.get(reverse("core:onboarding"))
        step = response.context["steps"][0]
        self.assertTrue(step["done"])
        self.assertEqual(step["action_url"], reverse("profiles:update", args=[profile.pk]))
        self.assertContains(response, "foldo-step--done")

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


class DashboardViewTests(SignedInTestCase):
    """The signed-in app shell must render a sensible empty state."""

    def test_dashboard_redirects_visitors_to_login(self):
        self.client.logout()
        url = reverse("core:dashboard")
        response = self.client.get(url)
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False
        )

    def test_dashboard_page_returns_200(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_page_uses_expected_template(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertTemplateUsed(response, "core/dashboard.html")
        self.assertTemplateUsed(response, "base.html")

    def test_dashboard_shows_empty_profile_state_with_create_link(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertFalse(response.context["summary"]["has_profile"])
        self.assertContains(response, reverse("profiles:create"))
        self.assertContains(response, reverse("core:onboarding"))

    def test_dashboard_shows_own_profile_completeness(self):
        profile = MainProfile.objects.create(
            owner=self.user, full_name="Dev Three", headline="Backend developer"
        )
        response = self.client.get(reverse("core:dashboard"))
        summary = response.context["summary"]
        self.assertTrue(summary["has_profile"])
        self.assertEqual(summary["profile_completeness"], 66)
        self.assertEqual(summary["missing_fields"], ["Contact email"])
        self.assertContains(response, "Dev Three")
        self.assertContains(response, reverse("profiles:update", args=[profile.pk]))

    def test_dashboard_never_shows_another_users_profile(self):
        other = get_user_model().objects.create_user(username="other", password="pw-Foldo-12345")
        MainProfile.objects.create(owner=other, full_name="Someone Else")
        response = self.client.get(reverse("core:dashboard"))
        self.assertFalse(response.context["summary"]["has_profile"])
        self.assertNotContains(response, "Someone Else")

    def test_dashboard_shows_empty_portfolio_state(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.context["summary"]["portfolios"], [])
        self.assertContains(response, reverse("rendering:gallery"))

    def test_dashboard_page_has_no_placeholder_links(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(response, 'href="#"')

    def test_dashboard_link_is_in_the_shared_navigation(self):
        html = self.client.get(reverse("core:dashboard")).content.decode()
        nav = html[html.index("<header"):html.index("</header>")]
        self.assertIn(reverse("core:dashboard"), nav)
        self.assertIn('aria-current="page"', nav)


class NavbarTests(TestCase):
    """The shared navbar shows the right links for visitors and members."""

    def _nav(self):
        html = self.client.get("/no-such-page/").content.decode()  # 404 keeps the shell
        return html[html.index("<header"):html.index("</header>")]

    def test_visitor_sees_log_in_and_sign_up_only(self):
        nav = self._nav()
        self.assertIn(reverse("accounts:login"), nav)
        self.assertIn(reverse("accounts:register"), nav)
        self.assertNotIn(reverse("core:dashboard"), nav)
        self.assertNotIn(reverse("accounts:logout"), nav)

    def test_member_sees_dashboard_settings_and_log_out(self):
        user = get_user_model().objects.create_user(username="dev3", password="pw-Foldo-12345")
        self.client.force_login(user)
        nav = self._nav()
        self.assertIn(reverse("core:dashboard"), nav)
        self.assertIn(reverse("profiles:list"), nav)
        self.assertIn(reverse("accounts:settings"), nav)
        self.assertIn(reverse("accounts:logout"), nav)
        self.assertNotIn(reverse("accounts:register"), nav)

    def test_log_out_is_a_post_form_inside_a_list_item(self):
        user = get_user_model().objects.create_user(username="dev3", password="pw-Foldo-12345")
        self.client.force_login(user)
        nav = self._nav()
        form = nav.index('action="' + reverse("accounts:logout"))
        self.assertNotIn("</li>", nav[nav.rindex("<li", 0, form):form])
        self.assertIn('method="post"', nav[nav.rindex("<form", 0, form):form])
        self.assertIn("csrfmiddlewaretoken", nav)


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
        self.assertIn(resolve_url(settings.LOGIN_URL), response.url)
        



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
    path("accounts/", include("apps.accounts.urls")),
    path("forbidden/", _always_forbidden),
]


@override_settings(ROOT_URLCONF="apps.core.tests")
class PermissionDeniedPageTests(TestCase):
    def test_custom_403_page_is_used(self):
        response = self.client.get("/forbidden/")
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้", status_code=403)



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



# ---------------------------------------------------------------------------
# FOLDO-10: date order (apps/core/validators.py -> validate_date_order)
# ---------------------------------------------------------------------------


class _DateRangeForm(forms.Form):
    """Test-only form that uses validate_date_order like a real FOLDO form would."""

    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)

    def clean(self):
        cleaned = super().clean()
        try:
            validate_date_order(cleaned.get("start_date"), cleaned.get("end_date"))
        except ValidationError as error:
            self.add_error("end_date", error)
        return cleaned


class DateOrderTests(SimpleTestCase):
    def test_end_before_start_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_date_order(date(2026, 5, 1), date(2026, 4, 30))

    def test_same_day_and_later_end_are_allowed(self):
        validate_date_order(date(2026, 5, 1), date(2026, 5, 1))  # must not raise
        validate_date_order(date(2026, 5, 1), date(2026, 6, 1))  # must not raise

    def test_empty_dates_are_allowed(self):
        """Still studying / still working: one or both dates may be blank."""
        validate_date_order(date(2026, 5, 1), None)
        validate_date_order(None, date(2026, 5, 1))
        validate_date_order(None, None)

    def test_form_shows_the_error_under_end_date(self):
        form = _DateRangeForm(data={"start_date": "2026-05-01", "end_date": "2026-04-30"})
        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)



# ---------------------------------------------------------------------------
# FOLDO-15: Project Story display (templates/partials/project_story.html)
# ---------------------------------------------------------------------------
# No Project model yet, so a SimpleNamespace stands in for a project.


def _project(**story):
    fields = {"problem": "", "role": "", "process": "", "solution": "", "outcome": ""}
    fields.update(story)
    return SimpleNamespace(**fields)


class ProjectStoryDisplayTests(SimpleTestCase):
    def _render(self, project):
        template = Template('{% include "partials/project_story.html" with project=project %}')
        return template.render(Context({"project": project}))

    def test_full_story_shows_all_five_parts_in_order(self):
        html = self._render(_project(
            problem="Slow sign-up", role="Backend dev", process="Interviews",
            solution="One-page form", outcome="2x more sign-ups",
        ))
        positions = [html.index(label) for label in ("ปัญหา", "บทบาท", "วิธีทำ", "ทางออก", "ผลลัพธ์")]
        self.assertEqual(positions, sorted(positions))

    def test_only_filled_parts_are_shown(self):
        html = self._render(_project(problem="Slow sign-up", outcome="2x more sign-ups"))
        self.assertIn("ปัญหา", html)
        self.assertIn("ผลลัพธ์", html)
        self.assertNotIn("บทบาท", html)
        self.assertNotIn("วิธีทำ", html)
        self.assertNotIn("ทางออก", html)

    def test_old_project_without_story_shows_nothing(self):
        """Old projects have no story data: the page must still work."""
        html = self._render(_project())
        self.assertNotIn("<section", html)

    def test_story_text_is_escaped_and_keeps_line_breaks(self):
        html = self._render(_project(problem="<script>x</script>\nsecond line"))
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<br>", html)