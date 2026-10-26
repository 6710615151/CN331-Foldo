"""
Data access layer for the ``core`` app (pure reads, no side effects).

``core`` owns no models. Its one real read is the health check, which only
asks whether dependencies respond and deliberately reports coarse booleans so
the endpoint never leaks environment variables, credentials or host details.
The rest of this module is fixed mock data for the app shell (see the "MOCK
DATA" section below) until ``apps.profiles`` / ``apps.portfolios`` exist.
Domain queries belong in each app's own ``selectors.py``.
"""

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError


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
# MOCK DATA — app shell preview (FOLDO-02 app shell slice)
# ---------------------------------------------------------------------------
# apps.profiles (FOLDO-03) and apps.portfolios (FOLDO-04) do not exist yet, so
# the dashboard and onboarding shell render against fixed mock data instead of
# a selector backed by real models. Every function below is tagged "MOCK" in
# its docstring so it is easy to grep for and replace once the owning app
# lands; nothing here performs a database query.


def get_mock_onboarding_steps() -> list[dict]:
    """MOCK: the three-step first-time walkthrough shown at ``/onboarding/``.

    Replace with real content once FOLDO-03 (main profile) defines what a
    genuinely empty profile looks like.
    """
    return [
        {
            "number": 1,
            "title": "สร้างโปรไฟล์หลักของคุณ",
            "title_en": "Build your main profile",
            "description": "กรอกข้อมูลส่วนตัว การศึกษา ทักษะ และผลงานไว้ที่เดียว",
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


def get_mock_dashboard_summary() -> dict:
    """MOCK: the signed-in shell's dashboard summary at ``/dashboard/``.

    Shapes the empty/first-time state (no profile, no portfolios yet) so the
    shell, navigation and layout can be reviewed before FOLDO-03/04 exist.
    """
    return {
        "has_profile": False,
        "profile_completeness": 0,
        "portfolios": [],
    }
