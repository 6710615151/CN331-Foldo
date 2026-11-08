"""FOLDO-16: Quality Check of a portfolio version, against real models."""
from datetime import date
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.profiles.models import Experience, MainProfile, Project, Skill

from ..content_selection.services import save_selection
from ..models import Portfolio
from .checks import CHECKS, ERROR, INFO, WARNING, run_quality_check

User = get_user_model()
PASSWORD = "pass-12345"


def titles(report, severity=None):
    return [f.title for f in report.findings if severity is None or f.severity == severity]


def finding(report, text):
    return next(f for f in report.findings if text in f.title)


class QualityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password=PASSWORD)
        cls.bob = User.objects.create_user("bob", password=PASSWORD)
        cls.profile = MainProfile.objects.create(
            owner=cls.alice, full_name="Alice Doe", headline="Backend developer", is_default=True,
            contact_email="alice@example.com", bio="I build web apps.", location="Bangkok",
        )
        cls.skill = Skill.objects.create(profile=cls.profile, name="Python")
        cls.job = Experience.objects.create(
            profile=cls.profile, company="Acme", job_title="Intern", start_date=date(2025, 6, 1)
        )
        cls.project = Project.objects.create(
            profile=cls.profile, project_name="FOLDO", description="Portfolio builder.",
            project_url="https://example.com", problem="Re-typing CVs.", role="Lead", outcome="Saved time.",
        )

    def setUp(self):
        self.portfolio = Portfolio.objects.create(owner=self.alice, title="Backend jobs", template_key="modern")
        self.client.login(username="alice", password=PASSWORD)

    def add_education(self):
        """Education lives in apps.education today and on the profile after FOLDO-04 (#36)."""
        try:
            from apps.profiles.models import Education
        except ImportError:
            from apps.education.models import EducationEntry

            return EducationEntry.objects.create(owner=self.alice, level="undergraduate", institution="TU",
                                                 start_year=2022)
        return Education.objects.create(profile=self.profile, institution="TU", start_date=date(2022, 8, 1))


class RulesTests(QualityTestCase):
    def test_a_complete_version_has_no_errors_or_warnings(self):
        self.add_education()
        report = run_quality_check(self.portfolio)
        self.assertEqual(titles(report, ERROR), [])
        self.assertEqual(titles(report, WARNING), [])
        self.assertFalse(report.is_blocking)

    def test_missing_required_fields_are_warnings_linked_to_the_profile_form(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(headline="", contact_email="")
        report = run_quality_check(self.portfolio)
        self.assertIn("ยังไม่ได้กรอกหัวข้อแนะนำตัว", titles(report, WARNING))
        self.assertIn("ยังไม่ได้กรอกอีเมลติดต่อ", titles(report, WARNING))
        self.assertEqual(finding(report, "หัวข้อแนะนำตัว").fix_url, reverse("profiles:update", args=[self.profile.pk]))

    def test_recommended_fields_are_suggestions(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(bio="", location="")
        report = run_quality_check(self.portfolio)
        self.assertIn("ยังไม่มีประวัติย่อ (About)", titles(report, INFO))
        self.assertIn("ยังไม่ได้ระบุที่อยู่หรือจังหวัด", titles(report, INFO))
        self.assertIn("ยังไม่มีรูปโปรไฟล์", titles(report, INFO))

    def test_very_long_bio_is_flagged(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(bio="x" * 1600)
        self.assertIn("ประวัติย่อค่อนข้างยาว", titles(run_quality_check(self.portfolio), INFO))

    def test_photo_record_without_a_file_is_a_warning(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(photo="profile_photos/missing.png")
        self.assertIn("ไม่พบไฟล์รูปโปรไฟล์", titles(run_quality_check(self.portfolio), WARNING))

    def test_malformed_profile_link_is_an_error(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(github_url="ftp://github.com/alice")
        report = run_quality_check(self.portfolio)
        self.assertIn("ลิงก์ GitHub ไม่ถูกต้อง", titles(report, ERROR))
        self.assertTrue(report.is_blocking)

    def test_malformed_project_link_only_counts_when_the_project_is_shown(self):
        Project.objects.filter(pk=self.project.pk).update(project_url="javascript:alert(1)")
        report = run_quality_check(self.portfolio)
        bad = finding(report, "ลิงก์ของโปรเจกต์")
        self.assertEqual(bad.severity, ERROR)
        self.assertEqual(bad.fix_url, reverse("profiles:project_edit", args=[self.project.pk]))

        save_selection(self.portfolio, {"skills": [self.skill.pk]})  # this version leaves the project out
        self.assertNotIn("ลิงก์ของโปรเจกต์ “FOLDO” ไม่ถูกต้อง", titles(run_quality_check(self.portfolio)))

    def test_section_with_no_data_is_a_warning_linked_to_its_edit_screen(self):
        Skill.objects.all().delete()
        report = run_quality_check(self.portfolio)
        skills = finding(report, "ยังไม่มีข้อมูลส่วนทักษะ")
        self.assertEqual(skills.severity, WARNING)
        self.assertEqual(skills.fix_url, reverse("profiles:skills_experience", args=[self.profile.pk]))
        self.assertEqual(finding(report, "ส่วนการศึกษา").severity, WARNING)
        self.assertTrue(finding(report, "ส่วนการศึกษา").fix_url)

    def test_section_left_out_on_purpose_is_only_a_suggestion(self):
        save_selection(self.portfolio, {"skills": [self.skill.pk], "projects": [self.project.pk]})
        report = run_quality_check(self.portfolio)
        left_out = finding(report, "ไม่ได้เลือกส่วนประสบการณ์")
        self.assertEqual(left_out.severity, INFO)
        self.assertEqual(left_out.fix_url, reverse("portfolios:content", args=[self.portfolio.pk]))

    def test_empty_version_is_an_error(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(bio="")
        save_selection(self.portfolio, {})
        report = run_quality_check(self.portfolio)
        self.assertIn("พอร์ตโฟลิโอว่างเปล่า", titles(report, ERROR))

    def test_version_without_any_profile_is_an_error(self):
        carol = User.objects.create_user("carol", password=PASSWORD)
        report = run_quality_check(Portfolio.objects.create(owner=carol, title="Empty"))
        self.assertEqual(titles(report, ERROR), ["พอร์ตโฟลิโอนี้ยังไม่มีโปรไฟล์"])
        self.assertEqual(report.errors[0].fix_url, reverse("profiles:create"))

    def test_selected_item_that_was_deleted_is_reported(self):
        save_selection(self.portfolio, {"skills": [self.skill.pk], "projects": [self.project.pk]})
        Skill.objects.filter(pk=self.skill.pk).delete()
        report = run_quality_check(self.portfolio)
        self.assertIn("ข้อมูลที่เลือกไว้ในส่วนทักษะถูกลบไปแล้ว", titles(report, WARNING))

    def test_project_story_missing_core_parts_is_a_suggestion(self):
        Project.objects.filter(pk=self.project.pk).update(outcome="")
        item = finding(run_quality_check(self.portfolio), "Project Story")
        self.assertEqual(item.severity, INFO)
        self.assertIn("ผลลัพธ์", item.detail)

    def test_project_without_any_story_is_not_nagged(self):
        Project.objects.filter(pk=self.project.pk).update(problem="", role="", outcome="")
        self.assertNotIn("Project Story", " ".join(titles(run_quality_check(self.portfolio))))

    def test_retired_template_is_a_warning(self):
        Portfolio.objects.filter(pk=self.portfolio.pk).update(template_key="midnight")
        self.portfolio.refresh_from_db()
        self.assertIn("เทมเพลตที่เลือกไว้ไม่มีแล้ว", titles(run_quality_check(self.portfolio), WARNING))

    def test_rendering_failure_is_an_error(self):
        with mock.patch("apps.portfolios.quality.checks.render_version_html", side_effect=RuntimeError("boom")), \
                self.assertLogs("apps.portfolios.quality.checks", level="ERROR"):
            report = run_quality_check(self.portfolio)
        self.assertIn("แสดงผลด้วยเทมเพลต Modern ไม่สำเร็จ", titles(report, ERROR))

    def test_a_crashing_check_does_not_stop_the_others(self):
        def broken(ctx):
            raise RuntimeError("boom")

        with self.assertLogs("apps.portfolios.quality.checks", level="ERROR"):
            report = run_quality_check(self.portfolio, checks=(("ทดสอบ", broken), *CHECKS))
        self.assertIn("ตรวจหัวข้อ “ทดสอบ” ไม่สำเร็จ", titles(report, WARNING))

    def test_findings_are_grouped_by_severity(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(github_url="ftp://x", headline="", bio="")
        report = run_quality_check(self.portfolio)
        severities = [f.severity for f in report.findings]
        self.assertEqual(severities, sorted(severities, key=[ERROR, WARNING, INFO].index))
        self.assertEqual([g[0] for g in report.groups], [ERROR, WARNING, INFO])


class PageTests(QualityTestCase):
    def url(self, portfolio=None):
        return reverse("portfolios:quality", args=[(portfolio or self.portfolio).pk])

    def test_page_shows_grouped_findings_with_fix_links(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(github_url="ftp://x")
        response = self.client.get(self.url())
        self.assertContains(response, "ยังไม่พร้อมส่ง")
        self.assertContains(response, "ต้องแก้ก่อนส่ง")
        self.assertContains(response, "ลิงก์ GitHub ไม่ถูกต้อง")
        self.assertContains(response, reverse("profiles:update", args=[self.profile.pk]))

    def test_checking_never_changes_data_or_publishes(self):
        before = Portfolio.objects.values().get(pk=self.portfolio.pk)
        with CaptureQueriesContext(connection) as queries:
            self.client.get(self.url())
            run_quality_check(self.portfolio)
        writes = [q["sql"] for q in queries
                  if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                  and "django_session" not in q["sql"]]
        self.assertEqual(writes, [])
        self.assertEqual(Portfolio.objects.values().get(pk=self.portfolio.pk), before)
        self.assertFalse(Portfolio.objects.get(pk=self.portfolio.pk).is_published)

    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post(self.url()).status_code, 405)

    def test_rerunning_after_an_edit_shows_the_new_result(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(headline="")
        self.assertContains(self.client.get(self.url()), "ยังไม่ได้กรอกหัวข้อแนะนำตัว")
        MainProfile.objects.filter(pk=self.profile.pk).update(headline="Backend developer")
        self.assertNotContains(self.client.get(self.url()), "ยังไม่ได้กรอกหัวข้อแนะนำตัว")
        self.assertContains(self.client.get(self.url()), f'href="{self.url()}"')  # "check again" link

    def test_reached_from_the_list_and_the_preview_bar(self):
        self.assertContains(self.client.get(reverse("portfolios:list")), self.url())
        self.assertContains(self.client.get(reverse("portfolios:preview", args=[self.portfolio.pk])), self.url())

    def test_another_user_gets_404(self):
        self.client.logout()
        self.client.login(username="bob", password=PASSWORD)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse(settings.LOGIN_URL), response["Location"])
