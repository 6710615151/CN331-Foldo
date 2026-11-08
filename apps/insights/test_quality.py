"""Tests for the Portfolio Quality Check (FOLDO-16)."""

import shutil
import tempfile
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.profiles.models import MainProfile

from .quality import ERROR, INFO, WARNING, run_quality_check

PASSWORD = "pw-Foldo-12345"


def make_user(username):
    return get_user_model().objects.create_user(username=username, password=PASSWORD)


def row(pk, **fields):
    return SimpleNamespace(pk=pk, **fields)


def providers(**sections):
    keys = ("skills", "experience", "education", "projects")
    return {key: (lambda _p, rows=sections.get(key, ()): rows) for key in keys}


class Rows:
    def __init__(self, *rows):
        self.rows = list(rows)

    def all(self):
        return self.rows


FULL_SECTIONS = providers(
    skills=[row(1, name="Python", proficiency="advanced")],
    experience=[row(2, job_title="Intern", company="Acme", description="", start_date=None, end_date=None)],
    education=[row(3, institution="TU", degree="B.Eng.", field_of_study="CE", start_date=None, end_date=None)],
    projects=[row(4, project_name="FOLDO", description="Portfolio builder", project_url="https://x.dev",
                  start_date=None, end_date=None)],
)


class QualityRulesTests(TestCase):
    def setUp(self):
        self.user = make_user("alice")
        self.profile = MainProfile.objects.create(
            owner=self.user, full_name="Alice", headline="Dev", contact_email="a@example.com",
            bio="Short bio.", location="Bangkok",
        )

    def titles(self, report, severity=None):
        return [f.title for f in report.findings if severity is None or f.severity == severity]

    def test_complete_profile_with_all_sections_is_not_blocking(self):
        report = run_quality_check(self.profile, theme_key="classic", providers=FULL_SECTIONS)
        self.assertFalse(report.is_blocking)
        self.assertEqual(report.warnings, [])
        self.assertEqual(self.titles(report, INFO), ["ยังไม่มีรูปโปรไฟล์"])

    def test_empty_portfolio_is_a_blocking_error(self):
        self.profile.bio = ""
        self.profile.save()
        report = run_quality_check(self.profile, theme_key="classic", providers=providers())
        self.assertTrue(report.is_blocking)
        self.assertIn("พอร์ตโฟลิโอว่างเปล่า", self.titles(report, ERROR))

    def test_missing_recommended_fields_are_warnings_with_fix_links(self):
        bare = MainProfile.objects.create(owner=self.user, label="Bare", full_name="Bare")
        report = run_quality_check(bare, theme_key="classic", providers=FULL_SECTIONS)
        warnings = report.warnings
        self.assertEqual([f.title for f in warnings], ["ยังไม่ได้กรอก Headline", "ยังไม่ได้กรอก Contact email"])
        for finding in warnings:
            self.assertEqual(finding.fix_url, reverse("profiles:update", args=[bare.pk]))

    def test_empty_sections_are_warnings(self):
        report = run_quality_check(
            self.profile, theme_key="classic", providers=providers(skills=[row(1, name="Python")])
        )
        self.assertEqual(
            sorted(t for t in self.titles(report, WARNING) if t.startswith("ไม่มีข้อมูลส่วน")),
            ["ไม่มีข้อมูลส่วน Education", "ไม่มีข้อมูลส่วน Experience", "ไม่มีข้อมูลส่วน Projects"],
        )

    def test_bad_project_and_evidence_links_are_errors(self):
        project = row(4, project_name="FOLDO", description="x", project_url="javascript:alert(1)",
                      evidence=Rows(SimpleNamespace(file_url="ftp://files.example/demo.mp4")))
        report = run_quality_check(self.profile, theme_key="classic", providers=providers(projects=[project]))
        errors = self.titles(report, ERROR)
        self.assertIn("ลิงก์ของผลงาน “FOLDO” ไม่ถูกต้อง", errors)
        self.assertIn("หลักฐานของผลงาน “FOLDO” มีลิงก์ไม่ถูกต้อง", errors)

    def test_bad_profile_link_saved_outside_the_form_is_an_error(self):
        MainProfile.objects.filter(pk=self.profile.pk).update(github_url="ftp://github.com/alice")
        self.profile.refresh_from_db()
        report = run_quality_check(self.profile, theme_key="classic", providers=FULL_SECTIONS)
        self.assertIn("ลิงก์ GitHub ไม่ถูกต้อง", self.titles(report, ERROR))

    def test_unknown_template_is_an_error(self):
        report = run_quality_check(self.profile, theme_key="neon", providers=FULL_SECTIONS)
        self.assertIn("ไม่พบเทมเพลตที่เลือก", self.titles(report, ERROR))

    def test_selection_of_deleted_items_is_a_warning(self):
        report = run_quality_check(
            self.profile, theme_key="classic", providers=FULL_SECTIONS, selected={"skills": [1, 99]}
        )
        self.assertIn("มีข้อมูลที่เลือกไว้ถูกลบไปแล้ว (Skills)", self.titles(report, WARNING))

    def test_selection_limits_what_counts_as_present(self):
        report = run_quality_check(
            self.profile, theme_key="classic", providers=FULL_SECTIONS, selected={"skills": [1]}
        )
        self.assertIn("ไม่มีข้อมูลส่วน Projects", self.titles(report, WARNING))

    def test_project_hints(self):
        story = SimpleNamespace(problem="P", role="", process="", solution="", outcome="")
        project = row(4, project_name="FOLDO", description="", project_url="", story=story)
        report = run_quality_check(self.profile, theme_key="classic", providers=providers(projects=[project]))
        infos = self.titles(report, INFO)
        self.assertIn("ผลงาน “FOLDO” ยังไม่มีคำอธิบาย", infos)
        self.assertIn("Project Story ของ “FOLDO” ยังกรอกไม่ครบ", infos)

    def test_long_bio_hint(self):
        self.profile.bio = "x" * 1600
        report = run_quality_check(self.profile, theme_key="classic", providers=FULL_SECTIONS)
        self.assertIn("ประวัติย่อค่อนข้างยาว", self.titles(report, INFO))

    def test_render_failure_is_reported_not_raised(self):
        with mock.patch("apps.insights.quality.render_portfolio_html", side_effect=RuntimeError("boom")):
            report = run_quality_check(self.profile, theme_key="modern", providers=FULL_SECTIONS)
        self.assertIn("แสดงผลด้วยเทมเพลต Modern ไม่สำเร็จ", self.titles(report, ERROR))

    def test_a_crashing_check_becomes_a_finding(self):
        def broken(_ctx):
            raise ValueError("bug")

        report = run_quality_check(self.profile, theme_key="classic", providers=FULL_SECTIONS,
                                   checks=(("broken rule", broken),))
        self.assertEqual(self.titles(report), ["ตรวจหัวข้อ “broken rule” ไม่สำเร็จ"])

    def test_findings_are_ordered_errors_warnings_infos(self):
        bare = MainProfile.objects.create(owner=self.user, label="Bare", full_name="Bare")
        report = run_quality_check(bare, theme_key="neon", providers=providers())
        order = [f.severity for f in report.findings]
        self.assertEqual(order, sorted(order, key=[ERROR, WARNING, INFO].index))
        self.assertEqual([s for s, _ in report.groups], [ERROR, WARNING, INFO])

    def test_check_never_changes_the_profile(self):
        before = MainProfile.objects.filter(pk=self.profile.pk).values().get()
        run_quality_check(self.profile, theme_key="classic", providers=providers())
        self.assertEqual(MainProfile.objects.filter(pk=self.profile.pk).values().get(), before)


class MissingPhotoFileTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def test_photo_record_without_file_is_a_warning(self):
        user = make_user("pic")
        profile = MainProfile.objects.create(owner=user, full_name="Pic",
                                             photo=SimpleUploadedFile("a.png", b"x"))
        profile.photo.storage.delete(profile.photo.name)
        report = run_quality_check(profile, theme_key="classic", providers=providers())
        self.assertIn("ไม่พบไฟล์รูปโปรไฟล์", [f.title for f in report.warnings])


class QualityViewTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.profile = MainProfile.objects.create(owner=self.alice, full_name="Alice")
        self.bobs = MainProfile.objects.create(owner=self.bob, full_name="Bob Secret")
        self.url = reverse("insights:quality", args=[self.profile.pk])
        self.client.force_login(self.alice)

    def test_owner_runs_the_check(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ยังไม่พร้อมส่ง")
        self.assertContains(response, "ต้องแก้ก่อนส่ง")
        self.assertEqual(response.context["theme_key"], "classic")

    def test_theme_can_be_chosen_and_rerun(self):
        response = self.client.get(self.url, {"theme": "creative"})
        self.assertEqual(response.context["report"].theme_key, "creative")
        self.assertContains(response, "ตรวจอีกครั้ง")

    def test_unknown_theme_is_reported(self):
        response = self.client.get(self.url, {"theme": "<b>neon</b>"})
        self.assertContains(response, "ไม่พบเทมเพลตที่เลือก")
        self.assertNotContains(response, "<b>neon</b>")

    def test_unknown_version_is_404(self):
        self.assertEqual(self.client.get(self.url, {"version": "999"}).status_code, 404)

    def test_check_is_get_only(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_another_users_profile_is_404(self):
        response = self.client.get(reverse("insights:quality", args=[self.bobs.pk]))
        self.assertEqual(response.status_code, 404)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}", fetch_redirect_response=False)

    def test_dashboard_links_to_quality_check(self):
        self.assertContains(self.client.get(reverse("core:dashboard")), self.url)
