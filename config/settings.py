"""
FOLDO — Django settings.

A single settings module with environment-based behaviour, as recommended for
a project of this size. Development defaults keep SQLite + DEBUG on; setting
the documented environment variables switches the same module into a
production-safe configuration (PostgreSQL, secure cookies, no DEBUG).

Environment variables are read through the small ``env_*`` helpers below and
loaded from a local ``.env`` file when one is present. Never commit ``.env``.
"""

import os
from pathlib import Path
from config import secretpass
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Load a local .env file if it exists. Variables already set in the environment
# take precedence; .env is a developer convenience.
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
# Small helpers so settings stay readable and avoid magic strings everywhere.
# ---------------------------------------------------------------------------
def env_str(name: str, default: str = "") -> str:
    """Return an environment variable as a stripped string."""
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    """Return an environment variable as a boolean.

    Accepts the usual truthy spellings: 1/true/yes/on (case-insensitive).
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    """Return an environment variable as an int, falling back on bad input."""
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_list(name: str, default: list | None = None) -> list:
    """Return a comma-separated environment variable as a list of strings."""
    raw = os.environ.get(name)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core security settings
# ---------------------------------------------------------------------------
# In development a throw-away key is used so the project runs with zero setup.
# Any shared or production environment MUST provide DJANGO_SECRET_KEY.
SECRET_KEY = env_str(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-change-me-before-deploying-foldo",
)

DEBUG = env_bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "[::1]"],
)

# Needed when Django runs behind a TLS-terminating reverse proxy.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# One Django app per bounded context (modular monolith). Dependencies point
# one way; core is the shared shell. Domain apps (profiles, portfolios) are
# created with their own Issues (FOLDO-02 onwards).
LOCAL_APPS = [
    "apps.accounts",
    "apps.core",
]

# Custom user model from the very first migration (see apps/accounts/models.py).
AUTH_USER_MODEL = "accounts.CustomUser"

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

# Development-only apps (guarded by DEBUG so they can never be active in
# production):
#   django_watchfiles     — efficient OS-level file watching for runserver's
#                           autoreloader (much lower CPU than the default
#                           StatReloader, especially on macOS).
#   django_browser_reload — reload the browser when files change.
if DEBUG:
    INSTALLED_APPS += [
        "django_watchfiles",
        "django_browser_reload",
    ]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# In development, inject a script that reloads the browser whenever code,
# templates or static files change (see requirements-dev.txt). Appended last so
# it runs after any response-encoding middleware, and gated on DEBUG so it is
# never active in production.
if DEBUG:
    MIDDLEWARE.append(
        "django_browser_reload.middleware.BrowserReloadMiddleware"
    )

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# SQLite is the zero-setup default for local development. Setting DB_ENGINE to
# "postgresql" switches to PostgreSQL using the documented DB_* variables.
DB_ENGINE = env_str("DB_ENGINE", "sqlite").lower()

if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("DB_NAME", "foldo"),
            "USER": env_str("DB_USER", "foldo"),
            "PASSWORD": env_str("DB_PASSWORD"),
            "HOST": env_str("DB_HOST", "localhost"),
            "PORT": env_str("DB_PORT", "5432"),
            # Reuse connections for a short time to reduce per-request overhead.
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# Redis is used when REDIS_URL is provided; otherwise an
# in-process cache keeps local development free of extra services.
REDIS_URL = env_str("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "foldo-local",
        }
    }


# ---------------------------------------------------------------------------
# Authentication & sessions
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # Django needs to read the token in templates.
CSRF_COOKIE_SAMESITE = "Lax"


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env_str("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
# Source files live in /static; `collectstatic` gathers them into STATIC_ROOT.
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Console logging only (stdout). The level is
# configurable and defaults to a quieter WARNING level in production.
DJANGO_LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", "DEBUG" if DEBUG else "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": DJANGO_LOG_LEVEL,
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Production hardening
# ---------------------------------------------------------------------------
# Enabled automatically whenever DEBUG is off. This keeps development relaxed
# while making deployment secure, without ever disabling CSRF or the security
# middleware itself.
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 60 * 60 * 24 * 7)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    # Trust the X-Forwarded-Proto header set by a TLS-terminating reverse proxy.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Bootstrap has no ``alert-error``; map the error level to ``alert-danger``.
MESSAGE_TAGS = {40: "danger"}

# Version string surfaced by the health-check endpoint. Kept in settings so it
# is easy to bump and never leaks anything sensitive.
FOLDO_VERSION = env_str("FOLDO_VERSION", "0.1.0")

LOGIN_REDIRECT_URL = "/accounts/dashboard/"         # where to go after login
LOGOUT_REDIRECT_URL = "/accounts/login/"            # where to go after logout

# email setting 
# for this case use foldoportfolio@gmail.com

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'foldoportfolio@gmail.com'

# stash password in secretpass
# in production don't commit this password to git
# create the secretpass.py
# apppass = "yourapppass"

#EMAIL_HOST_PASSWORD = secretpass.apppass;
EMAIL_HOST_PASSWORD = "??????";

DEFAULT_FROM_EMAIL = 'foldoportfolio@gmail.com'

