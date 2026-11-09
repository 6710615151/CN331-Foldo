"""Thai authentication screens and the password change flow."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

PASSWORD = "pw-Foldo-12345"


class ThaiAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alice", email="alice@example.com", password=PASSWORD
        )

    def test_auth_pages_are_in_thai(self):
        expectations = {
            reverse("accounts:login"): "เข้าสู่ระบบ",
            reverse("accounts:register"): "สมัครสมาชิก",
            reverse("accounts:password_reset"): "ลืมรหัสผ่าน",
            reverse("accounts:password_reset_done"): "ตรวจสอบอีเมล",
            reverse("accounts:password_reset_complete"): "ตั้งรหัสผ่านใหม่เรียบร้อย",
        }
        for url, text in expectations.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, text)
                self.assertContains(response, 'lang="th"')
                self.assertNotContains(response, "Log In</h")

    def test_wrong_password_shows_a_thai_error(self):
        response = self.client.post(reverse("accounts:login"), {"username": "alice", "password": "nope"})
        self.assertContains(response, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        self.assertContains(response, 'class="alert alert-danger"')

    def test_login_still_redirects_to_the_dashboard(self):
        response = self.client.post(reverse("accounts:login"), {"username": "alice", "password": PASSWORD})
        self.assertRedirects(response, reverse("core:dashboard"), fetch_redirect_response=False)

    def test_register_errors_are_thai(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "ALICE", "email": "new@example.com", "password1": "12345678", "password2": "12345678",
        })
        self.assertContains(response, "ชื่อผู้ใช้นี้ถูกใช้แล้ว")
        self.assertContains(response, "รหัสผ่านต้องไม่เป็นตัวเลขล้วน")

    def test_register_password_mismatch_is_thai(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "newbie", "email": "new@example.com", "password1": PASSWORD, "password2": PASSWORD + "x",
        })
        self.assertContains(response, "รหัสผ่านทั้งสองช่องไม่ตรงกัน")


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alice", password=PASSWORD)
        self.client.force_login(self.user)
        self.url = reverse("accounts:password_change")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_change_keeps_the_session_and_redirects_to_settings(self):
        new = "An0ther-Foldo-pass"
        response = self.client.post(self.url, {"old_password": PASSWORD, "new_password1": new, "new_password2": new})
        self.assertRedirects(response, reverse("accounts:settings"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new))
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)

    def test_wrong_old_password_is_rejected_in_thai(self):
        response = self.client.post(self.url, {"old_password": "wrong", "new_password1": "x", "new_password2": "x"})
        self.assertContains(response, "รหัสผ่านปัจจุบันไม่ถูกต้อง")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))
