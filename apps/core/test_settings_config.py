"""Production configuration, tested by executing the real settings module.

``config/settings.py`` only runs its production branches (HTTPS, HSTS, secure
cookies, DATABASE_URL, the secret-key guard...) when the environment says so.
These tests load the file as a fresh module under a controlled environment, so
what Render will actually get is checked, not assumed.
"""

import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import clear_url_caches

SETTINGS_FILE = Path(__file__).resolve().parents[2] / "config" / "settings.py"

# Variables that change what settings.py does; each test starts from none of them.
CONTROLLED = (
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "RENDER_EXTERNAL_HOSTNAME",
    "DATABASE_URL",
    "DB_ENGINE",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_CONN_MAX_AGE",
    "REDIS_URL",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_SERVE_MEDIA",
    "DJANGO_MEDIA_ROOT",
)
PROD_KEY = "test-only-" + "k" * 60


def load_settings(**env):
    """Execute config/settings.py with exactly these overrides and return the module."""
    clean = {k: v for k, v in os.environ.items() if k not in CONTROLLED}
    clean.update(env)
    with mock.patch.dict(os.environ, clean, clear=True), mock.patch("dotenv.load_dotenv"):
        spec = importlib.util.spec_from_file_location("settings_under_test", SETTINGS_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class EnvHelperTests(SimpleTestCase):
    def setUp(self):
        self.s = load_settings()

    def test_env_bool(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(self.s.env_bool("X", default=True))
        for raw, expected in (("1", True), ("YES", True), (" on ", True), ("false", False), ("0", False)):
            with mock.patch.dict(os.environ, {"X": raw}):
                self.assertIs(self.s.env_bool("X"), expected, raw)

    def test_env_int_falls_back_on_bad_input(self):
        with mock.patch.dict(os.environ, {"N": "abc"}):
            self.assertEqual(self.s.env_int("N", 7), 7)
        with mock.patch.dict(os.environ, {"N": "42"}):
            self.assertEqual(self.s.env_int("N", 7), 42)

    def test_env_list(self):
        with mock.patch.dict(os.environ, {"L": ""}):
            self.assertEqual(self.s.env_list("L", ["a"]), ["a"])
        with mock.patch.dict(os.environ, {"L": " a.com , ,b.com "}):
            self.assertEqual(self.s.env_list("L"), ["a.com", "b.com"])


class DevelopmentDefaultsTests(SimpleTestCase):
    def test_debug_on_and_sqlite_by_default(self):
        s = load_settings()
        self.assertTrue(s.DEBUG)
        self.assertEqual(s.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertFalse(getattr(s, "SECURE_SSL_REDIRECT", False))

    def test_dev_tools_are_added_only_when_installed(self):
        with mock.patch("importlib.util.find_spec", return_value=object()):
            s = load_settings()
        self.assertIn("django_browser_reload", s.INSTALLED_APPS)
        self.assertIn("django_browser_reload.middleware.BrowserReloadMiddleware", s.MIDDLEWARE)


class ProductionSettingsTests(SimpleTestCase):
    def test_refuses_to_start_with_the_development_secret_key(self):
        with self.assertRaises(ImproperlyConfigured):
            load_settings(DJANGO_DEBUG="false")

    def test_debug_off_turns_on_https_hsts_and_secure_cookies(self):
        s = load_settings(DJANGO_DEBUG="false", DJANGO_SECRET_KEY=PROD_KEY)
        self.assertFalse(s.DEBUG)
        self.assertTrue(s.SECURE_SSL_REDIRECT)
        self.assertEqual(s.SECURE_HSTS_SECONDS, 60 * 60 * 24 * 7)
        self.assertTrue(s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE)
        self.assertEqual(s.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(s.SECURE_REDIRECT_EXEMPT, [r"^health/$"])  # Render's health check is plain HTTP
        self.assertEqual(
            s.STORAGES["staticfiles"]["BACKEND"], "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )

    def test_render_hostname_is_trusted_automatically(self):
        s = load_settings(RENDER_EXTERNAL_HOSTNAME="cn331-foldo.onrender.com")
        self.assertIn("cn331-foldo.onrender.com", s.ALLOWED_HOSTS)
        self.assertIn("https://cn331-foldo.onrender.com", s.CSRF_TRUSTED_ORIGINS)

    def test_database_url_selects_postgresql(self):
        s = load_settings(DATABASE_URL="postgres://foldo:pw@db.example.com:5432/foldo")
        db = s.DATABASES["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual((db["HOST"], db["NAME"], db["CONN_MAX_AGE"]), ("db.example.com", "foldo", 60))
        self.assertTrue(db["CONN_HEALTH_CHECKS"])

    def test_db_engine_variables_still_work(self):
        s = load_settings(DB_ENGINE="postgresql", DB_NAME="foldo_db", DB_HOST="pg")
        db = s.DATABASES["default"]
        self.assertEqual((db["ENGINE"], db["NAME"], db["HOST"]), ("django.db.backends.postgresql", "foldo_db", "pg"))

    def test_redis_url_switches_the_cache(self):
        s = load_settings(REDIS_URL="redis://cache:6379/0")
        self.assertEqual(s.CACHES["default"]["BACKEND"], "django.core.cache.backends.redis.RedisCache")


class UrlConfTests(TestCase):
    """Routes that exist only in some configurations (config/urls.py)."""

    def _reload_urls(self):
        import config.urls

        clear_url_caches()
        importlib.reload(config.urls)
        clear_url_caches()

    def tearDown(self):
        self._reload_urls()  # back to the normal routes for the next test

    def test_uploads_are_served_in_production_only_when_opted_in(self):
        import tempfile

        with tempfile.TemporaryDirectory() as media:
            Path(media, "photo.txt").write_text("hello")
            with override_settings(DEBUG=False, SERVE_MEDIA=True, MEDIA_ROOT=media):
                self._reload_urls()
                response = self.client.get("/media/photo.txt")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"".join(response.streaming_content), b"hello")
            with override_settings(DEBUG=False, SERVE_MEDIA=False, MEDIA_ROOT=media):
                self._reload_urls()
                self.assertEqual(self.client.get("/media/photo.txt").status_code, 404)

    def test_browser_reload_route_only_with_dev_tools(self):
        fake = types.ModuleType("django_browser_reload.urls")
        fake.urlpatterns = []
        fake.app_name = "django_browser_reload"
        with mock.patch.dict(
            sys.modules,
            {"django_browser_reload": types.ModuleType("django_browser_reload"), "django_browser_reload.urls": fake},
        ):
            with override_settings(DEBUG=True, DEV_TOOLS_INSTALLED=True):
                self._reload_urls()
                import config.urls

                self.assertTrue(any("__reload__" in str(p.pattern) for p in config.urls.urlpatterns))
