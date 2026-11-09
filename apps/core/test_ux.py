"""Tests for the UX layer: next-step guidance, wayfinding, the portfolio builder
stepper, "save and add another", the form error summary and in-use badges.

Each test drives real pages (or the public selector) the way a user would, so a
template or URL change that breaks a journey fails here.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.selectors import get_next_steps
from apps.portfolios.models import Portfolio, PortfolioContentSetup
from apps.profiles.models import Education, Experience, MainProfile, Project, Skill

PASSWORD = "pw-Foldo-12345"


class _Signed(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="dev", password=PASSWORD)
        self.other = User.objects.create_user(username="other", password=PASSWORD)
        self.client.force_login(self.user)

    def complete_profile(self, **extra):
        data = {"full_name": "Dev One", "headline": "Backend", "contact_email": "dev@example.com"}
        data.update(extra)
        return MainProfile.objects.create(owner=self.user, **data)


class NextStepsTests(_Signed):
    def keys(self, **kwargs):
        return [step["key"] for step in get_next_steps(self.user, **kwargs)]

    def test_new_user_starts_with_profile_then_portfolio(self):
        self.assertEqual(self.keys(), ["profile", "portfolio"])

    def test_incomplete_profile_links_to_the_first_missing_field(self):
        profile = MainProfile.objects.create(owner=self.user, full_name="Dev")
        step = get_next_steps(self.user)[0]
        self.assertEqual(step["key"], "profile_fields")
        self.assertTrue(step["required"])
        self.assertEqual(step["url"], reverse("profiles:update", args=[profile.pk]) + "#id_headline")
        self.assertIn("หัวข้อแนะนำตัว", step["detail"])

    def test_empty_sections_are_recommended_not_required(self):
        self.complete_profile()
        steps = get_next_steps(self.user)
        recommended = {s["key"] for s in steps if not s["required"]}
        self.assertTrue({"education", "skills", "projects", "experience", "photo"} <= recommended)
        # Required journey steps always come first.
        self.assertEqual([s["required"] for s in steps], sorted((s["required"] for s in steps), reverse=True))

    def test_project_without_story_is_suggested_with_a_deep_link(self):
        profile = self.complete_profile()
        project = Project.objects.create(profile=profile, project_name="Bus Tracker")
        step = next(s for s in get_next_steps(self.user) if s["key"] == "story")
        self.assertIn("Bus Tracker", step["title"])
        self.assertEqual(step["url"], reverse("profiles:project_edit", args=[project.pk]) + "#sec-story")

    def test_unpublished_portfolio_links_to_the_publish_switch(self):
        self.complete_profile()
        portfolio = Portfolio.objects.create(owner=self.user, title="V1")
        step = next(s for s in get_next_steps(self.user) if s["key"] == "publish")
        self.assertEqual(step["url"], reverse("portfolios:update", args=[portfolio.pk]) + "#id_is_published")

    def test_bell_shows_required_steps_only(self):
        self.complete_profile()  # complete, but no education / skills / projects
        Portfolio.objects.create(owner=self.user, title="V1", is_published=True)
        self.assertEqual(self.keys(include_recommended=False), [])

    def test_steps_never_mention_another_users_rows(self):
        other_profile = MainProfile.objects.create(owner=self.other, full_name="Other")
        Project.objects.create(profile=other_profile, project_name="Secret project")
        self.complete_profile()
        self.assertNotIn("Secret project", str(get_next_steps(self.user)))

    def test_dashboard_renders_next_steps_and_hides_the_banner_after_first_version(self):
        self.complete_profile()
        response = self.client.get(reverse("core:dashboard"))
        self.assertContains(response, "สิ่งที่ควรทำต่อ")
        self.assertContains(response, "dash-banner-heading")  # no versions yet: show how it works
        Portfolio.objects.create(owner=self.user, title="V1")
        self.assertNotContains(self.client.get(reverse("core:dashboard")), "dash-banner-heading")

    def test_empty_dashboard_sections_link_to_their_add_forms(self):
        profile = self.complete_profile()
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn(reverse("profiles:education_add", args=[profile.pk]), html)
        self.assertIn(reverse("profiles:project_add", args=[profile.pk]), html)


class WayfindingTests(_Signed):
    def setUp(self):
        super().setUp()
        self.main = self.complete_profile(label="Main", is_default=True)
        self.design = MainProfile.objects.create(owner=self.user, label="Design", full_name="Dev")

    def sidebar(self, url):
        html = self.client.get(url).content.decode()
        return html[html.index("<header") : html.index("</header>")]

    def test_sidebar_sections_follow_the_profile_being_viewed(self):
        nav = self.sidebar(reverse("profiles:projects", args=[self.design.pk]))
        self.assertIn(reverse("profiles:education_list", args=[self.design.pk]), nav)
        self.assertNotIn(reverse("profiles:education_list", args=[self.main.pk]), nav)
        self.assertIn("Design", nav)  # the "which profile" chip, shown with 2+ profiles

    def test_sidebar_follows_the_profile_of_a_child_row(self):
        project = Project.objects.create(profile=self.design, project_name="Poster")
        nav = self.sidebar(reverse("profiles:project_edit", args=[project.pk]))
        self.assertIn(reverse("profiles:skills_experience", args=[self.design.pk]), nav)

    def test_sidebar_falls_back_to_default_elsewhere(self):
        nav = self.sidebar(reverse("portfolios:list"))
        self.assertIn(reverse("profiles:education_list", args=[self.main.pk]), nav)

    def test_profile_pages_share_a_section_nav_with_the_current_page_marked(self):
        pages = {
            reverse("profiles:view", args=[self.main.pk]): "ภาพรวม",
            reverse("profiles:education_list", args=[self.main.pk]): "การศึกษา",
            reverse("profiles:skills_experience", args=[self.main.pk]): "ทักษะและประสบการณ์",
            reverse("profiles:projects", args=[self.main.pk]): "โปรเจกต์",
        }
        for url, label in pages.items():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                nav = html[html.index('class="foldo-subnav"') :]
                nav = nav[: nav.index("</nav>")]
                current = nav[nav.index('aria-current="page"') :]
                self.assertIn(label, current[:200])
                self.assertIn("ว่าง", nav)  # empty sections are flagged

    def test_missing_profile_fields_link_to_the_field(self):
        html = self.client.get(reverse("profiles:view", args=[self.design.pk])).content.decode()
        self.assertIn(reverse("profiles:update", args=[self.design.pk]) + "#id_headline", html)


class BuilderStepperTests(_Signed):
    def setUp(self):
        super().setUp()
        self.complete_profile()
        self.portfolio = Portfolio.objects.create(owner=self.user, title="Backend")

    def test_every_builder_page_shows_the_stepper_with_its_step_current(self):
        pages = {
            "portfolios:update": "ตั้งค่าและดีไซน์",
            "portfolios:content": "เลือกเนื้อหา",
            "portfolios:device_preview": "ดูตัวอย่าง",
            "portfolios:quality": "ตรวจคุณภาพ",
            "portfolios:share": "เผยแพร่และแชร์",
        }
        for name, label in pages.items():
            with self.subTest(page=name):
                html = self.client.get(reverse(name, args=[self.portfolio.pk])).content.decode()
                flow = html[html.index('class="foldo-flow"') :]
                current = flow[flow.index('aria-current="step"') :]
                self.assertIn(label, current[:400])

    def test_stepper_reflects_real_state(self):
        url = reverse("portfolios:share", args=[self.portfolio.pk])
        self.assertContains(self.client.get(url), "ยังไม่เผยแพร่")
        self.assertContains(self.client.get(url), "แสดงทุกอย่าง")
        PortfolioContentSetup.objects.create(portfolio=self.portfolio)
        self.portfolio.is_published = True
        self.portfolio.save()
        html = self.client.get(url).content.decode()
        self.assertIn("เลือกเนื้อหาแล้ว", html)
        self.assertIn("เผยแพร่แล้ว", html)

    def test_create_page_shows_later_steps_as_locked(self):
        html = self.client.get(reverse("portfolios:create")).content.decode()
        self.assertEqual(html.count("is-locked"), 4)

    def test_unpublished_share_kit_points_at_the_publish_switch(self):
        response = self.client.get(reverse("portfolios:share", args=[self.portfolio.pk]))
        self.assertContains(response, reverse("portfolios:update", args=[self.portfolio.pk]) + "#id_is_published")

    def test_quality_page_suggests_publishing_when_nothing_blocks(self):
        response = self.client.get(reverse("portfolios:quality", args=[self.portfolio.pk]))
        report = response.context["report"]
        if not report.is_blocking:
            self.assertContains(response, "เผยแพร่เวอร์ชันนี้")
        self.assertContains(response, "ขั้นตอนถัดไป")

    def test_preview_toolbar_includes_content_and_share(self):
        html = self.client.get(reverse("portfolios:preview", args=[self.portfolio.pk])).content.decode()
        self.assertIn(reverse("portfolios:content", args=[self.portfolio.pk]), html)
        self.assertIn(reverse("portfolios:share", args=[self.portfolio.pk]), html)

    def test_another_users_portfolio_is_still_404(self):
        theirs = Portfolio.objects.create(owner=self.other, title="Theirs")
        for name in ("portfolios:update", "portfolios:content", "portfolios:quality", "portfolios:share"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=[theirs.pk])).status_code, 404)


class AddAnotherTests(_Signed):
    def setUp(self):
        super().setUp()
        self.profile = self.complete_profile()

    def test_save_and_add_another_returns_to_an_empty_form(self):
        pk = self.profile.pk
        cases = [
            ("profiles:education_add", {"institution": "KU", "start_date": "2022-08-01"}, Education),
            ("profiles:skill_add", {"name": "Python", "proficiency": "advanced"}, Skill),
            (
                "profiles:experience_add",
                {"company": "Agoda", "job_title": "Intern", "start_date": "2024-06-01"},
                Experience,
            ),
            ("profiles:project_add", {"project_name": "Bus Tracker"}, Project),
        ]
        for name, data, model in cases:
            with self.subTest(form=name):
                url = reverse(name, args=[pk])
                response = self.client.post(url, {**data, "add_another": "1"})
                self.assertRedirects(response, url)
                self.assertEqual(model.objects.filter(profile=self.profile).count(), 1)

    def test_plain_save_keeps_its_old_destination(self):
        response = self.client.post(
            reverse("profiles:skill_add", args=[self.profile.pk]), {"name": "Go", "proficiency": "beginner"}
        )
        self.assertRedirects(response, reverse("profiles:skills_experience", args=[self.profile.pk]))

    def test_invalid_add_another_stays_on_the_form_with_a_linked_error_summary(self):
        response = self.client.post(
            reverse("profiles:education_add", args=[self.profile.pk]),
            {"institution": "", "start_date": "2022-08-01", "add_another": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-error-summary")
        self.assertContains(response, 'href="#id_institution"')
        self.assertContains(response, 'value="2022-08-01"')  # entered data is kept

    def test_edit_pages_do_not_offer_add_another(self):
        skill = Skill.objects.create(profile=self.profile, name="SQL", proficiency="beginner")
        self.assertNotContains(self.client.get(reverse("profiles:skill_edit", args=[skill.pk])), 'name="add_another"')
        self.assertContains(
            self.client.get(reverse("profiles:skill_add", args=[self.profile.pk])), 'name="add_another"'
        )


class GalleryUsageTests(_Signed):
    def test_gallery_marks_templates_already_in_use(self):
        self.complete_profile()
        Portfolio.objects.create(owner=self.user, title="A", template_key="modern")
        Portfolio.objects.create(owner=self.user, title="B", template_key="modern")
        Portfolio.objects.create(owner=self.other, title="C", template_key="classic")
        response = self.client.get(reverse("rendering:gallery"))
        self.assertEqual(response.context["theme_usage"], {"modern": 2})
        self.assertContains(response, "ใช้อยู่ใน 2 พอร์ตโฟลิโอ")


class UnsavedGuardMarkupTests(_Signed):
    def test_editing_forms_opt_in_to_the_unsaved_changes_guard(self):
        profile = self.complete_profile()
        portfolio = Portfolio.objects.create(owner=self.user, title="V1")
        Project.objects.create(profile=profile, project_name="P", start_date=datetime.date(2024, 1, 1))
        urls = [
            reverse("profiles:update", args=[profile.pk]),
            reverse("profiles:education_add", args=[profile.pk]),
            reverse("profiles:skill_add", args=[profile.pk]),
            reverse("profiles:project_add", args=[profile.pk]),
            reverse("portfolios:update", args=[portfolio.pk]),
            reverse("accounts:settings"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "data-unsaved-guard")


class SaveFeedbackTests(_Signed):
    """Saving a portfolio lands on the full-page preview; the confirmation must show there."""

    def test_publish_confirmation_is_shown_on_the_page_the_user_lands_on(self):
        self.complete_profile()
        response = self.client.post(
            reverse("portfolios:create"),
            {"title": "Frontend Intern", "template_key": "modern", "is_published": "on"},
            follow=True,
        )
        self.assertContains(response, "pf-toolbar__msg")
        self.assertContains(response, "บันทึก “Frontend Intern” แล้ว (เผยแพร่แล้ว)")

    def test_public_page_never_shows_or_consumes_owner_messages(self):
        self.complete_profile()
        self.client.post(reverse("portfolios:create"), {"title": "V", "template_key": "modern", "is_published": "on"})
        portfolio = Portfolio.objects.get(title="V")
        public = self.client.get(reverse("portfolios:public", args=[portfolio.slug]))
        self.assertNotContains(public, "pf-toolbar__msg")
        # Still waiting for the owner's next app page.
        self.assertContains(self.client.get(reverse("portfolios:list")), "บันทึก “V” แล้ว")
