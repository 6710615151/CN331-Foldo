"""
Data access layer for the ``core`` app (pure reads, no side effects).

``core`` owns no models; its one read is the health check, which only asks
whether dependencies respond. It deliberately reports coarse booleans so the
endpoint never leaks environment variables, credentials or host details.
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
