"""Portfolio Quality Check (FOLDO-16).

``run_quality_check`` only reads: it never edits, saves or publishes anything.
Each check is isolated, so a check that crashes becomes a "could not run"
finding instead of an error page, and the user's data is untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.validators import safe_url_validator
from apps.rendering.selectors import (
    SECTION_SPECS,
    PortfolioContent,
    build_portfolio_content,
    default_providers,
)
from apps.rendering.services import render_portfolio_html
from apps.rendering.themes import PortfolioTheme, get_theme

from .sources import item_edit_url, section_add_url

logger = logging.getLogger(__name__)

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_ORDER = (ERROR, WARNING, INFO)
LONG_BIO = 1500
SECTION_LABELS = {key: title for key, title, _, _ in SECTION_SPECS}


@dataclass(frozen=True)
class Finding:
    severity: str
    title: str
    detail: str
    fix_url: str = ""
    fix_label: str = "แก้ไข"


@dataclass(frozen=True)
class QualityReport:
    findings: tuple[Finding, ...]
    theme_key: str

    def by_severity(self, severity: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    @property
    def errors(self) -> list[Finding]:
        return self.by_severity(ERROR)

    @property
    def warnings(self) -> list[Finding]:
        return self.by_severity(WARNING)

    @property
    def infos(self) -> list[Finding]:
        return self.by_severity(INFO)

    @property
    def is_blocking(self) -> bool:
        return bool(self.errors)

    @property
    def groups(self) -> list[tuple[str, list[Finding]]]:
        return [(s, self.by_severity(s)) for s in SEVERITY_ORDER if self.by_severity(s)]


@dataclass
class CheckContext:
    profile: object
    theme_key: str
    theme: PortfolioTheme | None
    rows: dict[str, list]
    selected: dict | None
    include_story: bool
    content: PortfolioContent | None = None
    edit_profile_url: str = field(default="")


def _is_bad_url(value: str) -> bool:
    if not value:
        return False
    try:
        safe_url_validator(value)
    except ValidationError:
        return True
    return False


# --- checks ------------------------------------------------------------------


def check_template(ctx: CheckContext) -> list[Finding]:
    if ctx.theme is not None:
        return []
    return [Finding(ERROR, "ไม่พบเทมเพลตที่เลือก",
                    f"ไม่มีเทมเพลตชื่อ “{ctx.theme_key}” พอร์ตโฟลิโอจะแสดงผลไม่ได้ ให้เลือกเทมเพลตใหม่",
                    reverse("rendering:gallery"), "เลือกเทมเพลต")]


def check_required_fields(ctx: CheckContext) -> list[Finding]:
    return [
        Finding(WARNING, f"ยังไม่ได้กรอก {label}",
                "ข้อมูลนี้แนะนำให้มีในทุกพอร์ตโฟลิโอ ผู้อ่านใช้ติดต่อหรือรู้ว่าคุณเป็นใคร",
                ctx.edit_profile_url, "แก้ไขโปรไฟล์")
        for label in ctx.profile.missing_fields
    ]


def check_recommended_fields(ctx: CheckContext) -> list[Finding]:
    profile, findings = ctx.profile, []
    if not (profile.bio or "").strip():
        findings.append(Finding(INFO, "ยังไม่มีประวัติย่อ (About)",
                                "ประวัติย่อ 2–3 ประโยคช่วยให้ผู้อ่านเข้าใจภาพรวมของคุณเร็วขึ้น",
                                ctx.edit_profile_url, "เพิ่มประวัติย่อ"))
    elif len(profile.bio) > LONG_BIO:
        findings.append(Finding(INFO, "ประวัติย่อค่อนข้างยาว",
                                f"ยาว {len(profile.bio)} ตัวอักษร อาจทำให้ PDF หน้าแรกแน่นเกินไป ลองย่อให้เหลือไม่เกิน {LONG_BIO}",
                                ctx.edit_profile_url, "แก้ประวัติย่อ"))
    if not profile.photo:
        findings.append(Finding(INFO, "ยังไม่มีรูปโปรไฟล์",
                                "เทมเพลตจะแสดงอักษรย่อแทนรูป", ctx.edit_profile_url, "เพิ่มรูป"))
    if not (profile.location or "").strip():
        findings.append(Finding(INFO, "ยังไม่ได้ระบุที่อยู่/จังหวัด", "ช่วยให้ผู้รับสมัครรู้ว่าคุณอยู่ที่ไหน",
                                ctx.edit_profile_url, "แก้ไขโปรไฟล์"))
    return findings


def check_photo_file(ctx: CheckContext) -> list[Finding]:
    photo = ctx.profile.photo
    if photo and not photo.storage.exists(photo.name):
        return [Finding(WARNING, "ไม่พบไฟล์รูปโปรไฟล์",
                        "ระบบบันทึกชื่อรูปไว้แต่หาไฟล์ไม่เจอ รูปจะไม่แสดง ให้อัปโหลดรูปใหม่",
                        ctx.edit_profile_url, "อัปโหลดรูปใหม่")]
    return []


def check_links(ctx: CheckContext) -> list[Finding]:
    profile, findings = ctx.profile, []
    for name, label in (("website", "Website"), ("linkedin_url", "LinkedIn"), ("github_url", "GitHub")):
        if _is_bad_url(getattr(profile, name, "")):
            findings.append(Finding(ERROR, f"ลิงก์ {label} ไม่ถูกต้อง",
                                    "ใช้ได้เฉพาะลิงก์ที่ขึ้นต้นด้วย http:// หรือ https:// ลิงก์นี้จะไม่แสดงในพอร์ตโฟลิโอ",
                                    ctx.edit_profile_url, "แก้ลิงก์"))
    for project in ctx.rows.get("projects", []):
        name = getattr(project, "project_name", "") or f"#{project.pk}"
        fix = item_edit_url(profile, "projects", project.pk)
        if _is_bad_url(getattr(project, "project_url", "")):
            findings.append(Finding(ERROR, f"ลิงก์ของผลงาน “{name}” ไม่ถูกต้อง",
                                    "ใช้ได้เฉพาะ http:// หรือ https:// ลิงก์นี้จะไม่แสดง", fix, "แก้ลิงก์"))
        evidence = getattr(project, "evidence", None)
        for item in evidence.all() if evidence is not None else ():
            if _is_bad_url(getattr(item, "file_url", "")):
                findings.append(Finding(ERROR, f"หลักฐานของผลงาน “{name}” มีลิงก์ไม่ถูกต้อง",
                                        "ใช้ได้เฉพาะ http:// หรือ https:// หลักฐานชิ้นนี้จะไม่แสดง", fix, "แก้ลิงก์"))
    return findings


def check_selection(ctx: CheckContext) -> list[Finding]:
    if ctx.selected is None:
        return []
    findings = []
    for key, ids in ctx.selected.items():
        existing = {row.pk for row in ctx.rows.get(key, [])}
        gone = sorted(set(ids) - existing)
        if gone:
            findings.append(Finding(WARNING, f"มีข้อมูลที่เลือกไว้ถูกลบไปแล้ว ({SECTION_LABELS.get(key, key)})",
                                    f"เลือกไว้ {len(gone)} รายการที่ไม่มีอยู่แล้ว จะไม่แสดงในพอร์ตโฟลิโอ",
                                    reverse("core:dashboard"), "ตรวจการเลือกเนื้อหา"))
    return findings


def check_sections(ctx: CheckContext) -> list[Finding]:
    content = ctx.content
    if content is None:
        return []
    if content.is_empty:
        return [Finding(ERROR, "พอร์ตโฟลิโอว่างเปล่า",
                        "ยังไม่มีประวัติย่อหรือข้อมูล section ไหนเลย เพิ่มข้อมูลหรือเลือกเนื้อหาก่อนส่งออก",
                        ctx.edit_profile_url, "เพิ่มข้อมูล")]
    present = {s.key for s in content.sections}
    return [
        Finding(WARNING, f"ไม่มีข้อมูลส่วน {title}",
                "section นี้จะไม่แสดงในพอร์ตโฟลิโอ ถ้าตำแหน่งที่สมัครต้องการ ควรเพิ่มหรือเลือกข้อมูล",
                section_add_url(ctx.profile, key), f"เพิ่ม {title}")
        for key, title, _, _ in SECTION_SPECS
        if key not in present
    ]


def check_project_details(ctx: CheckContext) -> list[Finding]:
    content = ctx.content
    projects = content.section("projects") if content else None
    findings = []
    for item in projects.items if projects else ():
        fix = item_edit_url(ctx.profile, "projects", item.id)
        if not item.description:
            findings.append(Finding(INFO, f"ผลงาน “{item.title}” ยังไม่มีคำอธิบาย",
                                    "เขียนสั้น ๆ ว่าผลงานนี้คืออะไรและคุณทำส่วนไหน", fix, "เพิ่มคำอธิบาย"))
        if ctx.include_story and 0 < len(item.story) < 3:
            findings.append(Finding(INFO, f"Project Story ของ “{item.title}” ยังกรอกไม่ครบ",
                                    "เรื่องเล่าที่มี Problem, Role และ Outcome ครบจะน่าเชื่อถือกว่า (ระบบไม่แต่งข้อมูลให้)",
                                    fix, "เติม Project Story"))
    return findings


def check_render(ctx: CheckContext) -> list[Finding]:
    if ctx.theme is None or ctx.content is None:
        return []
    try:
        render_portfolio_html(ctx.theme, ctx.content)
    except Exception:
        logger.exception("Quality check: rendering failed for profile %s", ctx.profile.pk)
        return [Finding(ERROR, f"แสดงผลด้วยเทมเพลต {ctx.theme.name} ไม่สำเร็จ",
                        "ข้อมูลบางส่วนทำให้เทมเพลตแสดงผลไม่ได้ ลองเปลี่ยนเทมเพลตหรือตรวจข้อมูลที่เพิ่งแก้",
                        reverse("rendering:gallery"), "เลือกเทมเพลตอื่น")]
    return []


CHECKS = (
    ("template", check_template),
    ("required fields", check_required_fields),
    ("recommended fields", check_recommended_fields),
    ("photo file", check_photo_file),
    ("links", check_links),
    ("selection", check_selection),
    ("sections", check_sections),
    ("project details", check_project_details),
    ("render", check_render),
)


def run_quality_check(profile, *, theme_key: str, selected=None, include_story: bool = True,
                      providers=None, checks=CHECKS) -> QualityReport:
    providers = providers or default_providers()
    rows = {key: list(providers.get(key, lambda _p: ())(profile)) for key, _, _, _ in SECTION_SPECS}
    frozen = {key: (lambda _p, r=r: r) for key, r in rows.items()}
    ctx = CheckContext(
        profile=profile,
        theme_key=theme_key,
        theme=get_theme(theme_key),
        rows=rows,
        selected=selected,
        include_story=include_story,
        edit_profile_url=reverse("profiles:update", args=[profile.pk]),
    )
    findings: list[Finding] = []
    try:
        ctx.content = build_portfolio_content(
            profile, selected=selected, include_story=include_story, providers=frozen
        )
    except Exception:
        logger.exception("Quality check: building content failed for profile %s", profile.pk)
        findings.append(Finding(ERROR, "อ่านข้อมูลโปรไฟล์ไม่สำเร็จ",
                                "ระบบอ่านข้อมูลบางส่วนไม่ได้ ข้อมูลของคุณยังอยู่ครบ ลองตรวจอีกครั้ง",
                                reverse("insights:quality", args=[profile.pk]), "ตรวจอีกครั้ง"))

    for name, check in checks:
        try:
            findings.extend(check(ctx))
        except Exception:
            logger.exception("Quality check '%s' failed for profile %s", name, profile.pk)
            findings.append(Finding(WARNING, f"ตรวจหัวข้อ “{name}” ไม่สำเร็จ",
                                    "ข้อนี้ตรวจไม่ได้ในครั้งนี้ ข้อมูลของคุณไม่ได้ถูกแก้ไข ลองกดตรวจอีกครั้ง",
                                    reverse("insights:quality", args=[profile.pk]), "ตรวจอีกครั้ง"))

    order = {severity: i for i, severity in enumerate(SEVERITY_ORDER)}
    findings.sort(key=lambda f: order[f.severity])
    return QualityReport(findings=tuple(findings), theme_key=theme_key)
