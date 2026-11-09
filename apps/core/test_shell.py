"""Tests for the redesigned app shell: real dashboard data, onboarding progress,
the sidebar/top-bar context, favicon and the shared template filters."""

import datetime

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.context_processors import shell
from apps.core.selectors import get_dashboard_summary, get_onboarding_steps, get_recent_activity
from apps.portfolios.models import Portfolio
from apps.profiles.models import MainProfile, Project, Skill

PASSWORD = "pw-Foldo-12345"


class _Users(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="dev", password=PASSWORD)
        self.other = User.objects.create_user(username="other", password=PASSWORD)
        self.client.force_login(self.user)


class DashboardDataTests(_Users):
    """Regression: the dashboard used to hard-code ``"portfolios": []``."""

    def test_dashboard_lists_the_users_own_portfolios(self):
        Portfolio.objects.create(owner=self.user, title="Backend jobs", is_published=True)
        Portfolio.objects.create(owner=self.user, title="Design jobs")
        Portfolio.objects.create(owner=self.other, title="Not mine")
        response = self.client.get(reverse("core:dashboard"))
        summary = response.context["summary"]
        self.assertEqual({p.title for p in summary["portfolios"]}, {"Backend jobs", "Design jobs"})
        self.assertEqual(summary["portfolio_count"], 2)
        self.assertEqual(summary["published_count"], 1)
        self.assertContains(response, "Backend jobs")
        self.assertNotContains(response, "Not mine")

    def test_dashboard_shows_at_most_three_latest_versions(self):
        for i in range(5):
            Portfolio.objects.create(owner=self.user, title=f"V{i}")
        summary = get_dashboard_summary(self.user)
        self.assertEqual(len(summary["portfolios"]), 3)
        self.assertEqual(summary["portfolio_count"], 5)

    def test_section_counts_come_from_the_default_profile(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="Dev")
        Skill.objects.create(profile=profile, name="Python")
        Project.objects.create(profile=profile, project_name="FOLDO")
        counts = get_dashboard_summary(self.user)["section_counts"]
        self.assertEqual(counts, {"education": 0, "skills": 1, "experience": 0, "projects": 1})

    def test_recent_activity_is_scoped_to_the_user(self):
        mine = MainProfile.objects.create(owner=self.user, full_name="Dev")
        theirs = MainProfile.objects.create(owner=self.other, full_name="Other")
        Skill.objects.create(profile=mine, name="Django")
        Skill.objects.create(profile=theirs, name="Secret skill")
        titles = [item["title"] for item in get_recent_activity(self.user)]
        self.assertIn("Django", titles)
        self.assertNotIn("Secret skill", titles)
        self.assertNotIn("Other", " ".join(titles))

    def test_next_step_follows_real_progress(self):
        self.assertEqual(get_dashboard_summary(self.user)["next_step"]["number"], 1)
        MainProfile.objects.create(owner=self.user, full_name="Dev")
        self.assertEqual(get_dashboard_summary(self.user)["next_step"]["number"], 2)
        portfolio = Portfolio.objects.create(owner=self.user, title="V1")
        self.assertEqual(get_dashboard_summary(self.user)["next_step"]["number"], 3)
        portfolio.is_published = True
        portfolio.save()
        summary = get_dashboard_summary(self.user)
        self.assertIsNone(summary["next_step"])
        self.assertEqual(summary["steps_done"], 3)


class OnboardingProgressTests(_Users):
    """Regression: steps 2 and 3 never completed and had no action."""

    def test_step_two_and_three_start_open(self):
        steps = get_onboarding_steps(self.user)
        self.assertFalse(steps[1]["done"])
        self.assertEqual(steps[1]["action_url"], reverse("portfolios:create"))
        self.assertFalse(steps[2]["done"])
        self.assertEqual(steps[2]["action_url"], "")

    def test_step_two_is_done_once_a_portfolio_exists(self):
        portfolio = Portfolio.objects.create(owner=self.user, title="V1")
        steps = get_onboarding_steps(self.user)
        self.assertTrue(steps[1]["done"])
        self.assertEqual(steps[1]["action_url"], reverse("portfolios:list"))
        self.assertFalse(steps[2]["done"])
        self.assertEqual(steps[2]["action_url"], reverse("portfolios:device_preview", args=[portfolio.pk]))

    def test_step_three_is_done_once_a_version_is_published(self):
        portfolio = Portfolio.objects.create(owner=self.user, title="V1", is_published=True)
        steps = get_onboarding_steps(self.user)
        self.assertTrue(steps[2]["done"])
        self.assertEqual(steps[2]["action_url"], reverse("portfolios:share", args=[portfolio.pk]))

    def test_another_users_portfolio_does_not_count(self):
        Portfolio.objects.create(owner=self.other, title="Theirs", is_published=True)
        steps = get_onboarding_steps(self.user)
        self.assertFalse(steps[1]["done"])
        self.assertFalse(steps[2]["done"])

    def test_page_marks_done_steps(self):
        MainProfile.objects.create(owner=self.user, full_name="Dev")
        Portfolio.objects.create(owner=self.user, title="V1", is_published=True)
        html = self.client.get(reverse("core:onboarding")).content.decode()
        self.assertEqual(html.count("foldo-step--done"), 3)


class ShellContextTests(_Users):
    def _shell(self, user, path="/dashboard/"):
        request = RequestFactory().get(path)
        request.user = user
        from django.urls import resolve

        request.resolver_match = resolve(path)
        return shell(request)["shell"]

    def test_visitors_get_no_shell(self):
        from django.contrib.auth.models import AnonymousUser

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        self.assertIsNone(shell(request)["shell"])

    def test_section_follows_the_current_route(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="Dev")
        cases = {
            "/dashboard/": "dashboard",
            reverse("profiles:education_list", args=[profile.pk]): "education",
            reverse("profiles:skills_experience", args=[profile.pk]): "skills",
            reverse("profiles:projects", args=[profile.pk]): "projects",
            reverse("profiles:view", args=[profile.pk]): "profile",
            reverse("portfolios:list"): "portfolios",
            reverse("rendering:gallery"): "templates",
            reverse("accounts:settings"): "settings",
        }
        for path, section in cases.items():
            with self.subTest(path=path):
                self.assertEqual(self._shell(self.user, path).section, section)

    def test_todos_are_real_and_scoped(self):
        todos = self._shell(self.user).todos
        self.assertEqual([t["url"] for t in todos], [reverse("profiles:create"), reverse("portfolios:create")])
        MainProfile.objects.create(owner=self.user, full_name="Dev", headline="x", contact_email="d@example.com")
        Portfolio.objects.create(owner=self.user, title="V1", is_published=True)
        self.assertEqual(self._shell(self.user).todos, [])

    def test_sidebar_links_go_to_the_default_profiles_sections(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="Dev")
        html = self.client.get(reverse("core:dashboard")).content.decode()
        nav = html[html.index("<header") : html.index("</header>")]
        for name in ("profiles:education_list", "profiles:skills_experience", "profiles:projects"):
            self.assertIn(reverse(name, args=[profile.pk]), nav)


class FaviconAndLegacyTests(TestCase):
    def test_favicon_is_linked_and_served(self):
        html = self.client.get(reverse("core:landing")).content.decode()
        self.assertIn('rel="icon"', html)
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("images/favicon.ico"))

    def test_legacy_accounts_dashboard_redirects_to_the_real_one(self):
        user = get_user_model().objects.create_user(username="dev", password=PASSWORD)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(response, reverse("core:dashboard"))


class TemplateFilterTests(TestCase):
    def render(self, source, **context):
        return Template("{% load foldo_tags %}" + source).render(Context(context)).strip()

    def test_th_month_and_date(self):
        day = datetime.date(2022, 8, 1)
        self.assertEqual(self.render("{{ d|th_month }}", d=day), "ส.ค. 2022")
        self.assertEqual(self.render("{{ d|th_date }}", d=day), "1 ส.ค. 2022")
        self.assertEqual(self.render("{{ d|th_month }}", d=None), "")

    def test_ago(self):
        now = timezone.now()
        self.assertEqual(self.render("{{ t|ago }}", t=now), "เมื่อสักครู่")
        self.assertEqual(self.render("{{ t|ago }}", t=now - datetime.timedelta(hours=3)), "3 ชม.ที่แล้ว")

    def test_domain_initial_level(self):
        self.assertEqual(self.render("{{ u|domain }}", u="https://www.github.com/foldo/"), "github.com/foldo")
        self.assertEqual(self.render("{{ s|initial }}", s=" resume rocket"), "R")
        self.assertEqual(self.render("{{ p|level }}", p="advanced"), "3")

    def test_file_url_is_empty_for_a_missing_file(self):
        profile = MainProfile(full_name="x")
        self.assertEqual(self.render("{{ f|file_url }}", f=profile.photo), "")
