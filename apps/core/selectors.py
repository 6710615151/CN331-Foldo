"""
Data access layer for the ``core`` app (pure reads, no side effects).

``core`` owns no models. Its one real read is the health check, which only
asks whether dependencies respond and deliberately reports coarse booleans so
the endpoint never leaks environment variables, credentials or host details.
The rest of this module composes the app shell's dashboard and onboarding
state from other apps' public services (``apps.profiles.services``); domain
queries themselves belong in each app's own module.
"""

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.urls import reverse

from apps.profiles.services import get_default_profile


class DatabaseHealthCheck:
    """Verifies that the configured database accepts a connection.

    Uses Django's ORM connection layer so it works identically for SQLite and
    PostgreSQL. Errors are swallowed and reported as a boolean: callers must
    never receive raw exception text through a public endpoint.
    """

    def __init__(self, alias: str = "default") -> None:
        self.alias = alias

    def is_healthy(self) -> bool:
        try:
            connections[self.alias].cursor()
        except OperationalError:
            return False
        return True


class HealthReport:
    """Collects individual checks into a single public payload.

    Designed so new checks (cache, storage, ...) can be added later without
    changing the view that serialises the report.
    """

    def __init__(self, version: str, checks: dict) -> None:
        self.version = version
        self.checks = checks

    @property
    def is_healthy(self) -> bool:
        return all(self.checks.values())

    def as_dict(self) -> dict:
        return {
            "status": "ok" if self.is_healthy else "degraded",
            "service": "foldo",
            "version": self.version,
            "checks": self.checks,
        }


def get_health_report() -> HealthReport:
    """Read the current health of FOLDO's dependencies (no side effects)."""
    checks = {
        "database": DatabaseHealthCheck().is_healthy(),
    }
    return HealthReport(version=settings.FOLDO_VERSION, checks=checks)


# ---------------------------------------------------------------------------
# App shell: onboarding steps and dashboard summary
# ---------------------------------------------------------------------------
# The Main Profile comes from apps.profiles (FOLDO-03). Portfolio versions
# arrive with FOLDO-05 (Sprint 3), so they are still an empty list here.


def get_onboarding_steps(user) -> list[dict]:
    """The three-step walkthrough at ``/onboarding/``.

    Step 1 is marked done once the user has a Main Profile. Steps 2 and 3 have
    no action until portfolio versions exist.
    """
    profile = get_default_profile(user)
    return [
        {
            "number": 1,
            "title": "สร้างโปรไฟล์หลักของคุณ",
            "title_en": "Build your main profile",
            "description": "กรอกข้อมูลส่วนตัว การศึกษา ทักษะ และผลงานไว้ที่เดียว",
            "done": profile is not None,
            "action_url": (
                reverse("profiles:update", args=[profile.pk])
                if profile
                else reverse("profiles:create")
            ),
            "action_label": "แก้ไขโปรไฟล์" if profile else "สร้างโปรไฟล์",
        },
        {
            "number": 2,
            "title": "สร้างพอร์ตโฟลิโอหลายเวอร์ชัน",
            "title_en": "Create tailored portfolio versions",
            "description": "เลือกเนื้อหาและเทมเพลตที่เหมาะกับงานหรือทุนที่สมัคร",
        },
        {
            "number": 3,
            "title": "ดูตัวอย่างและส่งออกเป็น PDF",
            "title_en": "Preview and export to PDF",
            "description": "ตรวจสอบพอร์ตโฟลิโอก่อนส่งออกหรือแชร์ลิงก์",
        },
    ]


def get_dashboard_summary(user) -> dict:
    """The signed-in user's dashboard: their Main Profile status, scoped to them."""
    profile = get_default_profile(user)
    return {
        "has_profile": profile is not None,
        "profile": profile,
        "profile_completeness": profile.completion_percent if profile else 0,
        "missing_fields": profile.missing_fields if profile else [],
        "portfolios": [],
    }
