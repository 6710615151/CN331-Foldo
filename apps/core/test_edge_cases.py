"""Edge cases and failure paths in core and accounts: the app shell must never take
a page down, the health check must report a dead database, and the small template
helpers must cope with empty or odd input."""

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.db.utils import OperationalError
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from apps.accounts.forms import SignUpForm
from apps.core import selectors
from apps.core.context_processors import _profile_for_route, shell
from apps.core.views import server_error
from apps.profiles.models import Education, MainProfile, Skill

PASSWORD = "pw-Foldo-12345"


def render(source, **context):
    return Template("{% load foldo_tags %}" + source).render(Context(context)).strip()


class TemplateFilterEdgeTests(SimpleTestCase):
    def test_empty_values_render_as_nothing(self):
        for source in ("{{ v|th_date }}", "{{ v|ago }}", "{{ v|domain }}"):
            with self.subTest(source=source):
                self.assertEqual(render(source, v=None), "")

    def test_th_date_with_time(self):
        moment = timezone.make_aware(datetime.datetime(2026, 11, 8, 14, 5))
        self.assertTrue(render('{{ t|th_date:"time" }}', t=moment).endswith("2026 14:05"))

    def test_ago_buckets(self):
        now = timezone.now()
        self.assertEqual(render("{{ t|ago }}", t=now - datetime.timedelta(minutes=5)), "5 นาทีที่แล้ว")
        self.assertEqual(render("{{ t|ago }}", t=now - datetime.timedelta(days=2)), "2 วันที่แล้ว")
        old = now - datetime.timedelta(days=40)
        self.assertEqual(render("{{ t|ago }}", t=old), render("{{ t|th_date }}", t=old))

    def test_defensive_filters(self):
        self.assertEqual(render("{% for i in v|times %}x{% endfor %}", v="not a number"), "")
        broken = mock.Mock(**{"__bool__": lambda self: True})
        type(broken).url = mock.PropertyMock(side_effect=ValueError)
        self.assertEqual(render("{{ f|file_url }}", f=broken), "")
        self.assertEqual(render("{{ f|errored_fields|length }}", f=object()), "0")
        self.assertEqual(render("{{ m|lookup:'x' }}", m="not a dict"), "0")


class ShellResilienceTests(TestCase):
    """A database hiccup in the sidebar or bell must not turn into a 500."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="shell", password=PASSWORD)

    def _shell(self, path="/dashboard/"):
        request = RequestFactory().get(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        return shell(request)["shell"]

    def test_database_errors_degrade_to_empty_values(self):
        with mock.patch("apps.profiles.services.get_default_profile", side_effect=DatabaseError):
            self.assertIsNone(self._shell().profile)
        with mock.patch("apps.core.selectors.get_next_steps", side_effect=DatabaseError):
            self.assertEqual(self._shell().todos, [])
        with mock.patch("apps.profiles.services.get_profiles", side_effect=DatabaseError):
            self.assertEqual(self._shell().profile_count, 0)

    def test_nav_profile_survives_a_failed_lookup(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="Shell")
        path = reverse("profiles:projects", args=[profile.pk])
        with mock.patch("apps.core.context_processors._profile_for_route", side_effect=DatabaseError):
            self.assertEqual(self._shell(path).nav_profile, profile)  # falls back to the default

    def test_photo_without_a_url_is_empty(self):
        MainProfile.objects.create(owner=self.user, full_name="Shell", photo="profile_photos/x.png")
        app = self._shell()
        with mock.patch("django.db.models.fields.files.FieldFile.url", new_callable=mock.PropertyMock) as url:
            url.side_effect = ValueError
            self.assertEqual(app.photo_url, "")

    def test_unknown_profile_route_resolves_to_no_profile(self):
        self.assertIsNone(_profile_for_route(self.user, "list", {"pk": 1}))


class SelectorEdgeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sel", password=PASSWORD)

    def test_health_check_reports_an_unreachable_database(self):
        dead = {"default": mock.Mock(cursor=mock.Mock(side_effect=OperationalError))}
        with mock.patch.object(selectors, "connections", dead):
            self.assertFalse(selectors.DatabaseHealthCheck().is_healthy())
            self.assertEqual(selectors.get_health_report().as_dict()["status"], "degraded")

    def test_complete_profile_has_no_first_missing_field(self):
        profile = MainProfile(full_name="A", headline="B", contact_email="a@example.com")
        self.assertEqual(selectors._first_missing_field(profile), "")

    def test_filled_profile_gets_no_section_recommendations(self):
        profile = MainProfile.objects.create(
            owner=self.user, full_name="A", headline="B", contact_email="a@example.com", photo="p.png"
        )
        Education.objects.create(profile=profile, institution="KU", start_date=datetime.date(2020, 1, 1))
        Skill.objects.create(profile=profile, name="Python")
        keys = {s["key"] for s in selectors.get_next_steps(self.user)}
        self.assertFalse(keys & {"education", "skills", "photo"})

    def test_projects_with_a_story_get_no_story_reminder(self):
        from apps.profiles.models import Project

        profile = MainProfile.objects.create(owner=self.user, full_name="A", headline="B", contact_email="a@e.com")
        Project.objects.create(profile=profile, project_name="Done", problem="p", role="r", outcome="o")
        self.assertNotIn("story", {s["key"] for s in selectors.get_next_steps(self.user)})

    def test_recent_activity_includes_education_and_skills(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="A")
        Education.objects.create(profile=profile, institution="KU", start_date=datetime.date(2020, 1, 1))
        Skill.objects.create(profile=profile, name="Python")
        from apps.profiles.models import Experience

        Experience.objects.create(profile=profile, company="KU", job_title="TA", start_date=datetime.date(2024, 1, 1))
        kinds = {item["kind"] for item in selectors.get_recent_activity(self.user)}
        self.assertTrue({"education", "skill", "experience", "profile"} <= kinds)


class ErrorPageTests(TestCase):
    def test_custom_500_page(self):
        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("ระบบขัดข้อง".encode(), response.content)


class AccountsEdgeTests(TestCase):
    def test_user_str_is_the_username(self):
        self.assertEqual(str(get_user_model()(username="mali")), "mali")

    def test_sign_up_form_can_save_without_committing(self):
        form = SignUpForm(
            data={
                "username": "newbie",
                "email": "n@example.com",
                "password1": "Str0ng-Pass!42",
                "password2": "Str0ng-Pass!42",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)
        self.assertIsNone(user.pk)
        self.assertEqual(user.email, "n@example.com")
