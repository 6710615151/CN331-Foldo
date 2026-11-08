"""
Data access layer for the ``core`` app (pure reads, no side effects).

``core`` owns no models. Its one real read is the health check, which only
asks whether dependencies respond and deliberately reports coarse booleans so
the endpoint never leaks environment variables, credentials or host details.
The rest of this module composes the app shell's dashboard and onboarding
state from other apps' public services (``apps.profiles.services`` and
``apps.portfolios.services``); everything is scoped to the signed-in user.
"""

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.urls import reverse

from apps.portfolios.services import get_portfolios
from apps.profiles.models import Education, Experience, Project, Skill
from apps.profiles.services import get_default_profile, get_profiles


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
# Everything below reads the signed-in user's own rows only: profiles through
# apps.profiles.services, portfolio versions through apps.portfolios.services.

DASHBOARD_PORTFOLIOS = 3
RECENT_ACTIVITY = 6


def get_progress(user) -> dict:
    """Where the user is in the profile → portfolio → share journey (3 small queries)."""
    profile = get_default_profile(user)
    portfolios = get_portfolios(user)
    latest = portfolios.first()  # Portfolio.Meta.ordering = ["-updated_at"]
    published = portfolios.filter(is_published=True).first()
    return {
        "profile": profile,
        "latest_portfolio": latest,
        "published_portfolio": published,
    }


def get_onboarding_steps(user, progress=None) -> list[dict]:
    """The three-step walkthrough at ``/onboarding/``.

    1. done once the user has a Main Profile;
    2. done once they have at least one portfolio version;
    3. done once a version is published (its share link and QR code work).
    Every step always offers the next useful action.
    """
    progress = progress or get_progress(user)
    profile = progress["profile"]
    latest = progress["latest_portfolio"]
    published = progress["published_portfolio"]

    if published:
        step3_url, step3_label = reverse("portfolios:share", args=[published.pk]), "แชร์ลิงก์และ QR"
    elif latest:
        step3_url, step3_label = reverse("portfolios:device_preview", args=[latest.pk]), "ดูตัวอย่าง"
    else:
        step3_url, step3_label = "", ""

    return [
        {
            "number": 1,
            "title": "สร้างโปรไฟล์",
            "title_en": "Build your main profile",
            "description": "เก็บข้อมูลส่วนตัว การศึกษา ทักษะ และโปรเจกต์ไว้ที่เดียว แก้ครั้งเดียว ทุกพอร์ตโฟลิโอเปลี่ยนตาม",
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
            "title": "สร้างพอร์ตโฟลิโอ",
            "title_en": "Create tailored portfolio versions",
            "description": "เลือกเทมเพลตและเนื้อหาให้ตรงกับงานหรือทุนที่จะสมัคร งานละหนึ่งพอร์ตโฟลิโอก็ได้",
            "done": latest is not None,
            "action_url": reverse("portfolios:list") if latest else reverse("portfolios:create"),
            "action_label": "ดูพอร์ตโฟลิโอของฉัน" if latest else "สร้างพอร์ตโฟลิโอ",
        },
        {
            "number": 3,
            "title": "ตรวจ แล้วแชร์",
            "title_en": "Preview, export and share",
            "description": "ดูตัวอย่างบนจอคอมและมือถือ ดาวน์โหลด PDF แล้วเผยแพร่เพื่อส่งลิงก์หรือ QR code ให้ผู้รับสมัคร",
            "done": published is not None,
            "action_url": step3_url,
            "action_label": step3_label,
        },
    ]


PROFILE_FIELD_LABELS_TH = {
    "full_name": "ชื่อ-นามสกุล",
    "headline": "หัวข้อแนะนำตัว",
    "contact_email": "อีเมลติดต่อ",
}


def profile_missing_labels(profile) -> list[str]:
    """``profile.missing_fields`` in Thai, in the same order (for UI copy)."""
    if profile is None:
        return []
    return [PROFILE_FIELD_LABELS_TH.get(name, label)
            for name, label in profile.REQUIRED_FOR_PORTFOLIO.items()
            if not (getattr(profile, name) or "").strip()]


def _first_missing_field(profile) -> str:
    for name in profile.REQUIRED_FOR_PORTFOLIO:
        if not (getattr(profile, name) or "").strip():
            return name
    return ""


def _step(key, title, detail, url, icon, tone, *, required, action):
    return {"key": key, "title": title, "detail": detail, "url": url, "icon": icon,
            "tone": tone, "required": required, "action": action}


def get_next_steps(user, *, include_recommended=True, profile=None, portfolios=None) -> list[dict]:
    """Ordered, actionable next steps built only from the user's own rows.

    ``required`` steps block the profile → portfolio → share journey (they drive
    the bell in the top bar). Recommended steps make a portfolio stronger
    (education, skills, projects, Project Story, experience, photo). Every step
    links straight to the page (and, where possible, the field) that fixes it.
    """
    profile = profile if profile is not None else get_default_profile(user)
    portfolios = portfolios if portfolios is not None else get_portfolios(user)
    steps = []

    if profile is None:
        steps.append(_step(
            "profile", "สร้างโปรไฟล์", "เริ่มจากชื่อและหัวข้อแนะนำตัว ที่เหลือเติมทีหลังได้",
            reverse("profiles:create"), "user", "lime", required=True, action="สร้างโปรไฟล์"))
    elif not profile.is_complete:
        missing = profile_missing_labels(profile)
        steps.append(_step(
            "profile_fields", "กรอกโปรไฟล์ให้ครบ",
            f"ยังขาด {', '.join(missing)} (ครบ {profile.completion_percent}%)",
            reverse("profiles:update", args=[profile.pk]) + f"#id_{_first_missing_field(profile)}",
            "user", "pink", required=True, action="กรอก"))

    recommended = []
    if include_recommended and profile is not None:
        pk = profile.pk
        if not profile.educations.exists():
            recommended.append(_step(
                "education", "เพิ่มการศึกษา", "สถาบันและสาขาช่วยให้ผู้อ่านเข้าใจพื้นฐานของคุณ",
                reverse("profiles:education_add", args=[pk]), "cap", "blue", required=False, action="เพิ่ม"))
        if not profile.skills.exists():
            recommended.append(_step(
                "skills", "เพิ่มทักษะ", "ใส่ 5–8 ทักษะหลักพร้อมระดับความชำนาญ",
                reverse("profiles:skill_add", args=[pk]), "spark", "purple", required=False, action="เพิ่ม"))
        projects = list(profile.projects.all()[:20])
        if not projects:
            recommended.append(_step(
                "projects", "เพิ่มโปรเจกต์แรก", "โปรเจกต์คือหลักฐานว่าคุณทำงานได้จริง",
                reverse("profiles:project_add", args=[pk]), "code", "pink", required=False, action="เพิ่ม"))
        else:
            no_story = [p for p in projects if not p.has_story]
            if no_story:
                first = no_story[0]
                more = f" (ยังเหลืออีก {len(no_story) - 1} โปรเจกต์)" if len(no_story) > 1 else ""
                recommended.append(_step(
                    "story", f"เล่า Project Story ของ “{first.project_name}”",
                    f"บอกปัญหา บทบาท และผลลัพธ์ ให้ผู้อ่านเห็นวิธีทำงานของคุณ{more}",
                    reverse("profiles:project_edit", args=[first.pk]) + "#sec-story",
                    "book", "pink", required=False, action="เขียน"))

    latest = portfolios.first()
    if latest is None:
        steps.append(_step(
            "portfolio", "สร้างพอร์ตโฟลิโอแรก", "เลือกเทมเพลตให้เหมาะกับงานที่จะสมัคร ใช้เวลาไม่ถึงนาที",
            reverse("portfolios:create"), "layers", "blue", required=True, action="สร้าง"))
    elif not portfolios.filter(is_published=True).exists():
        steps.append(_step(
            "publish", f"เผยแพร่ “{latest.title}”", "เพื่อรับลิงก์สาธารณะและ QR code ไว้ส่งให้ผู้รับสมัคร",
            reverse("portfolios:update", args=[latest.pk]) + "#id_is_published",
            "share", "purple", required=True, action="เผยแพร่"))

    if include_recommended and profile is not None:
        if not profile.experiences.exists():
            recommended.append(_step(
                "experience", "เพิ่มประสบการณ์ (ถ้ามี)", "งานประจำ ฝึกงาน พาร์ตไทม์ หรืองานอาสา นับได้ทั้งหมด",
                reverse("profiles:experience_add", args=[profile.pk]), "briefcase", "magenta",
                required=False, action="เพิ่ม"))
        if not profile.photo:
            recommended.append(_step(
                "photo", "ใส่รูปโปรไฟล์", "ไม่บังคับ แต่ช่วยให้ผู้อ่านจำคุณได้",
                reverse("profiles:update", args=[profile.pk]) + "#id_photo", "image", "purple",
                required=False, action="อัปโหลด"))

    # Required steps first (the journey), then what makes the portfolio stronger.
    return steps + recommended


def _activity(kind, label, title, url, obj, icon, tone):
    created = obj.created_at
    updated = obj.updated_at
    is_new = abs((updated - created).total_seconds()) < 2
    return {
        "kind": kind,
        "label": label,
        "title": title,
        "url": url,
        "at": updated,
        "verb": "เพิ่ม" if is_new else "แก้ไข",
        "icon": icon,
        "tone": tone,
    }


def get_recent_activity(user, limit=RECENT_ACTIVITY) -> list[dict]:
    """The user's most recently added or edited rows across profiles and portfolios.

    Reads at most ``limit`` rows per table (6 small queries), then merges them.
    """
    items = []
    for profile in get_profiles(user).order_by("-updated_at")[:limit]:
        items.append(_activity("profile", "โปรไฟล์", profile.label,
                               reverse("profiles:view", args=[profile.pk]), profile, "user", "blue"))
    owned = {"profile__owner": user}
    for row in Education.objects.filter(**owned).order_by("-updated_at")[:limit]:
        items.append(_activity("education", "การศึกษา", row.institution,
                               reverse("profiles:education_list", args=[row.profile_id]), row, "cap", "blue"))
    for row in Skill.objects.filter(**owned).order_by("-updated_at")[:limit]:
        items.append(_activity("skill", "ทักษะ", row.name,
                               reverse("profiles:skills_experience", args=[row.profile_id]), row, "spark", "purple"))
    for row in Experience.objects.filter(**owned).order_by("-updated_at")[:limit]:
        items.append(_activity("experience", "ประสบการณ์", f"{row.job_title} · {row.company}",
                               reverse("profiles:skills_experience", args=[row.profile_id]), row, "briefcase", "purple"))
    for row in Project.objects.filter(**owned).order_by("-updated_at")[:limit]:
        items.append(_activity("project", "โปรเจกต์", row.project_name,
                               reverse("profiles:project_detail", args=[row.pk]), row, "code", "pink"))
    for row in get_portfolios(user).order_by("-updated_at")[:limit]:
        items.append(_activity("portfolio", "พอร์ตโฟลิโอ", row.title,
                               reverse("portfolios:device_preview", args=[row.pk]), row, "layers", "lime"))
    items.sort(key=lambda item: item["at"], reverse=True)
    return items[:limit]


def get_dashboard_summary(user) -> dict:
    """The signed-in user's dashboard, built only from their own rows."""
    progress = get_progress(user)
    profile = progress["profile"]
    portfolios = get_portfolios(user)
    steps = get_onboarding_steps(user, progress)
    next_step = next((step for step in steps if not step["done"] and step["action_url"]), None)

    section_counts = {}
    if profile is not None:
        section_counts = {
            "education": profile.educations.count(),
            "skills": profile.skills.count(),
            "experience": profile.experiences.count(),
            "projects": profile.projects.count(),
        }

    next_steps = get_next_steps(user, profile=profile, portfolios=portfolios)

    return {
        "has_profile": profile is not None,
        "profile": profile,
        "profile_completeness": profile.completion_percent if profile else 0,
        "missing_fields": profile.missing_fields if profile else [],
        "missing_labels": profile_missing_labels(profile),
        "next_steps": next_steps[:4],
        "next_steps_more": max(0, len(next_steps) - 4),
        "required_steps": [s for s in next_steps if s["required"]],
        "section_counts": section_counts,
        "portfolios": list(portfolios.select_related("profile")[:DASHBOARD_PORTFOLIOS]),
        "portfolio_count": portfolios.count(),
        "published_count": portfolios.filter(is_published=True).count(),
        "steps": steps,
        "steps_done": sum(1 for step in steps if step["done"]),
        "next_step": next_step,
        "recent_activity": get_recent_activity(user),
    }
