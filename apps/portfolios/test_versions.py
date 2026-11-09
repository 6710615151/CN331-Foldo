"""FOLDO-05: create, rename and delete portfolio versions; persistence, ownership and status."""

from datetime import date
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from apps.profiles.models import Experience, MainProfile, Project, Skill

from .models import Portfolio

User = get_user_model()
PASSWORD = "pass-12345"


def form_data(**overrides):
    data = {"title": "Backend jobs", "profile": "", "template_key": "classic"}
    data.update(overrides)
    return data


class VersionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password=PASSWORD)
        cls.bob = User.objects.create_user("bob", password=PASSWORD)
        cls.profile = MainProfile.objects.create(owner=cls.alice, full_name="Alice Doe", is_default=True)
        cls.bob_profile = MainProfile.objects.create(owner=cls.bob, full_name="Bob Roe", is_default=True)

    def setUp(self):
        self.client.login(username="alice", password=PASSWORD)

    def create(self, **overrides):
        return self.client.post(reverse("portfolios:create"), form_data(**overrides))


class CreateVersionTests(VersionTestCase):
    def test_user_can_create_two_versions(self):
        self.create(title="Backend jobs", template_key="modern")
        self.create(title="Design jobs", template_key="creative")
        versions = Portfolio.objects.filter(owner=self.alice).order_by("title")
        self.assertEqual(
            [(v.title, v.template_key) for v in versions], [("Backend jobs", "modern"), ("Design jobs", "creative")]
        )
        self.assertNotEqual(versions[0].slug, versions[1].slug)

        response = self.client.get(reverse("portfolios:list"))
        self.assertContains(response, "Backend jobs")
        self.assertContains(response, "Design jobs")

    def test_create_redirects_to_preview_with_a_saved_message(self):
        response = self.create()
        portfolio = Portfolio.objects.get()
        preview = reverse("portfolios:preview", args=[portfolio.pk])
        self.assertRedirects(response, preview, fetch_redirect_response=False)
        # The confirmation shows on the page the user lands on (the preview's owner bar).
        self.assertContains(self.client.get(preview), "แล้ว (ยังไม่เผยแพร่)")

    def test_owner_always_comes_from_the_signed_in_user(self):
        self.create(owner=self.bob.pk)
        self.assertEqual(Portfolio.objects.get().owner, self.alice)

    def test_new_version_is_private_by_default(self):
        self.create()
        self.assertFalse(Portfolio.objects.get().is_published)

    def test_title_is_trimmed(self):
        self.create(title="   Backend jobs   ")
        self.assertEqual(Portfolio.objects.get().title, "Backend jobs")

    def test_blank_title_is_rejected_and_other_input_is_kept(self):
        response = self.create(title="   ", template_key="creative")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Portfolio.objects.exists())
        self.assertContains(response, "ต้องกรอกช่องนี้")
        self.assertContains(response, "is-invalid")
        self.assertRegex(response.content.decode(), r'value="creative"\s+id="id_template_key_creative" checked')

    def test_another_users_profile_cannot_be_chosen(self):
        response = self.create(profile=self.bob_profile.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ตัวเลือกนี้ใช้ไม่ได้แล้ว")
        self.assertFalse(Portfolio.objects.exists())

    def test_database_error_keeps_the_input(self):
        with (
            mock.patch.object(Portfolio, "save", side_effect=DatabaseError("down")),
            self.assertLogs("apps.portfolios.views", level="ERROR"),
        ):
            response = self.create(title="Kept title")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ระบบขัดข้องชั่วคราว")
        self.assertContains(response, 'value="Kept title"')
        self.assertFalse(Portfolio.objects.exists())


class RenameAndStatusTests(VersionTestCase):
    def setUp(self):
        super().setUp()
        self.backend = Portfolio.objects.create(owner=self.alice, title="Backend jobs", template_key="modern")
        self.design = Portfolio.objects.create(owner=self.alice, title="Design jobs", template_key="creative")

    def edit(self, portfolio, **overrides):
        data = form_data(title=portfolio.title, template_key=portfolio.template_key)
        data.update(overrides)
        return self.client.post(reverse("portfolios:update", args=[portfolio.pk]), data)

    def test_rename_is_saved_and_other_versions_are_unchanged(self):
        response = self.edit(self.backend, title="Backend internships")
        self.assertRedirects(response, reverse("portfolios:preview", args=[self.backend.pk]))
        self.backend.refresh_from_db()
        self.design.refresh_from_db()
        self.assertEqual(self.backend.title, "Backend internships")
        self.assertEqual((self.design.title, self.design.template_key), ("Design jobs", "creative"))

    def test_rename_keeps_the_public_link(self):
        slug = self.backend.slug
        self.edit(self.backend, title="New name")
        self.backend.refresh_from_db()
        self.assertEqual(self.backend.slug, slug)

    def test_edit_form_shows_the_saved_values(self):
        response = self.client.get(reverse("portfolios:update", args=[self.backend.pk]))
        self.assertContains(response, 'value="Backend jobs"')
        self.assertRegex(response.content.decode(), r'value="modern"\s+id="id_template_key_modern" checked')

    def test_publish_and_unpublish_change_the_status(self):
        self.edit(self.backend, is_published="on")
        self.backend.refresh_from_db()
        self.assertTrue(self.backend.is_published)
        list_page = self.client.get(reverse("portfolios:list"))
        self.assertContains(list_page, "เผยแพร่แล้ว")
        self.assertContains(list_page, self.backend.public_path)

        self.edit(self.backend)  # checkbox left out = off
        self.backend.refresh_from_db()
        self.assertFalse(self.backend.is_published)
        self.client.logout()
        self.assertEqual(self.client.get(self.backend.public_path).status_code, 404)

    def test_versions_persist_across_logout_and_login(self):
        self.edit(self.backend, title="Saved for later")
        self.client.logout()
        self.client.login(username="alice", password=PASSWORD)
        self.assertContains(self.client.get(reverse("portfolios:list")), "Saved for later")


class DeleteVersionTests(VersionTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.skill = Skill.objects.create(profile=cls.profile, name="Python")
        cls.job = Experience.objects.create(
            profile=cls.profile, company="Acme", job_title="Intern", start_date=date(2025, 6, 1)
        )
        cls.project = Project.objects.create(profile=cls.profile, project_name="FOLDO", role="Team lead")

    def setUp(self):
        super().setUp()
        self.backend = Portfolio.objects.create(owner=self.alice, title="Backend jobs", profile=self.profile)
        self.design = Portfolio.objects.create(owner=self.alice, title="Design jobs", profile=self.profile)
        self.url = reverse("portfolios:delete", args=[self.backend.pk])

    def test_get_asks_for_confirmation_and_deletes_nothing(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Backend jobs")
        self.assertTrue(Portfolio.objects.filter(pk=self.backend.pk).exists())

    def test_deleting_a_version_never_deletes_main_profile_records(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("portfolios:list"))
        self.assertFalse(Portfolio.objects.filter(pk=self.backend.pk).exists())

        self.assertTrue(MainProfile.objects.filter(pk=self.profile.pk).exists())
        self.assertTrue(Skill.objects.filter(pk=self.skill.pk).exists())
        self.assertTrue(Experience.objects.filter(pk=self.job.pk).exists())
        project = Project.objects.get(pk=self.project.pk)
        self.assertEqual(project.role, "Team lead")

    def test_deleting_one_version_leaves_the_others(self):
        self.client.post(self.url)
        self.assertTrue(Portfolio.objects.filter(pk=self.design.pk).exists())
        self.assertEqual(self.client.get(reverse("portfolios:preview", args=[self.design.pk])).status_code, 200)

    def test_deleted_version_is_gone_everywhere(self):
        slug = self.backend.slug
        self.client.post(self.url)
        self.assertEqual(self.client.get(reverse("portfolios:preview", args=[self.backend.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("portfolios:public", args=[slug])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("portfolios:list")), "Backend jobs")

    def test_database_error_keeps_the_version(self):
        with (
            mock.patch.object(Portfolio, "delete", side_effect=DatabaseError("down")),
            self.assertLogs("apps.portfolios.views", level="ERROR"),
        ):
            response = self.client.post(self.url, follow=True)
        self.assertContains(response, "ลบพอร์ตโฟลิโอไม่สำเร็จ")
        self.assertTrue(Portfolio.objects.filter(pk=self.backend.pk).exists())

    def test_deleting_the_profile_keeps_the_version(self):
        other = MainProfile.objects.create(owner=self.alice, full_name="Alice Two", label="Two")
        self.backend.profile = other
        self.backend.save()
        other.delete()
        self.backend.refresh_from_db()
        self.assertIsNone(self.backend.profile)  # falls back to the default profile
        response = self.client.get(reverse("portfolios:preview", args=[self.backend.pk]))
        self.assertContains(response, "Alice Doe")


class OwnershipTests(VersionTestCase):
    def setUp(self):
        super().setUp()
        self.backend = Portfolio.objects.create(owner=self.alice, title="Backend jobs")

    def owner_urls(self):
        return [
            reverse(name, args=[self.backend.pk])
            for name in ("portfolios:update", "portfolios:delete", "portfolios:preview")
        ]

    def test_list_shows_only_my_versions(self):
        Portfolio.objects.create(owner=self.bob, title="Bob's secret version")
        response = self.client.get(reverse("portfolios:list"))
        self.assertContains(response, "Backend jobs")
        self.assertNotContains(response, "Bob&#x27;s secret version")

    def test_empty_list_offers_to_create_one(self):
        self.client.logout()
        self.client.login(username="bob", password=PASSWORD)
        response = self.client.get(reverse("portfolios:list"))
        self.assertContains(response, "ยังไม่มีพอร์ตโฟลิโอ")
        self.assertContains(response, reverse("portfolios:create"))

    def test_another_user_gets_404_and_changes_nothing(self):
        self.client.logout()
        self.client.login(username="bob", password=PASSWORD)
        for url in self.owner_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse("portfolios:update", args=[self.backend.pk]), form_data(title="Hacked")
            ).status_code,
            404,
        )
        self.assertEqual(self.client.post(reverse("portfolios:delete", args=[self.backend.pk])).status_code, 404)
        self.backend.refresh_from_db()
        self.assertEqual(self.backend.title, "Backend jobs")

    def test_visitor_is_sent_to_login(self):
        self.client.logout()
        for url in [reverse("portfolios:list"), reverse("portfolios:create"), *self.owner_urls()]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse(settings.LOGIN_URL), response["Location"])
        self.client.post(reverse("portfolios:delete", args=[self.backend.pk]))
        self.assertTrue(Portfolio.objects.filter(pk=self.backend.pk).exists())
