"""Portfolio Quality Check (FOLDO-16), run on one portfolio version.

``run_quality_check(portfolio)`` only reads. It never saves, edits, deletes or
publishes anything, so running it again after an edit is always safe.

It checks the version as it will really be shown (and exported): its own
profile, content selection and template, through the same
``build_version_content`` / ``render_version_html`` the preview uses.

Every check is isolated: a check that crashes becomes a "could not check"
finding instead of an error page.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.core.selectors import profile_missing_labels
from apps.core.validators import safe_url_validator
from apps.rendering.selectors import SECTION_SPECS
from apps.rendering.themes import get_theme

from ..services import build_version_content, render_version_html, resolve_profile, selected_ids, theme_for

logger = logging.getLogger(__name__)

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_ORDER = (ERROR, WARNING, INFO)
SEVERITY_LABELS = {ERROR: "ต้องแก้ก่อนส่ง", WARNING: "ควรแก้", INFO: "คำแนะนำ"}
SECTION_TITLES = {key: title for key, title, _, _ in SECTION_SPECS}
# The portfolio document keeps English headings; findings are UI text, so Thai (docs/CONTENT_GUIDE.md).
SECTION_TITLES_TH = {"experience": "ประสบการณ์", "education": "การศึกษา", "projects": "โปรเจกต์", "skills": "ทักษะ"}
STORY_LABELS_TH = {"Problem": "ปัญหา", "My role": "บทบาท", "Process": "วิธีทำ", "Solution": "ทางออก", "Outcome": "ผลลัพธ์"}
LONG_BIO = 1500
STORY_CORE = ("Problem", "My role", "Outcome")  # what a reader needs to trust a project story


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
    checked_at: object

    def by_severity(self, severity):
        return [f for f in self.findings if f.severity == severity]

    @property
    def errors(self):
        return self.by_severity(ERROR)

    @property
    def warnings(self):
        return self.by_severity(WARNING)

    @property
    def infos(self):
        return self.by_severity(INFO)

    @property
    def is_blocking(self):
        return bool(self.errors)

    @property
    def score(self):
        """0–100 readiness for the summary ring. Anything blocking keeps it under 50."""
        value = 100 - 25 * len(self.errors) - 8 * len(self.warnings) - 2 * len(self.infos)
        if self.errors:
            value = min(value, 49)
        return max(0, value)

    @property
    def groups(self):
        """[(severity, label, findings)] in severity order, empty groups left out."""
        return [(s, SEVERITY_LABELS[s], self.by_severity(s)) for s in SEVERITY_ORDER if self.by_severity(s)]


@dataclass
class CheckContext:
    portfolio: object
    profile: object
    selected: dict | None
    content: object = None
    urls: dict = field(default_factory=dict)


# --- helpers -----------------------------------------------------------------


def _is_bad_url(value) -> bool:
    if not value:
        return False
    try:
        safe_url_validator(value)
    except ValidationError:
        return True
    return False


def _first_url(*candidates) -> str:
    """The first route that exists. Lets one link survive while a screen moves between apps."""
    for name, args in candidates:
        try:
            return reverse(name, args=args)
        except NoReverseMatch:
            continue
    return ""


def _fix_urls(portfolio, profile) -> dict:
    urls = {
        "version": reverse("portfolios:update", args=[portfolio.pk]),
        "content": _first_url(("portfolios:content", [portfolio.pk])),
        "create_profile": reverse("profiles:create"),
    }
    if profile is not None:
        pk = profile.pk
        urls.update(
            profile=reverse("profiles:update", args=[pk]),
            skills=reverse("profiles:skills_experience", args=[pk]),
            experience=reverse("profiles:skills_experience", args=[pk]),
            projects=reverse("profiles:projects", args=[pk]),
            # Education is moving onto the profile (FOLDO-04, PR #36); until then it is per user.
            education=_first_url(("profiles:education_list", [pk]), ("education:settings", [])),
        )
    return urls


# --- checks ------------------------------------------------------------------


def check_profile_exists(ctx):
    if ctx.profile is not None:
        return []
    return [Finding(ERROR, "พอร์ตโฟลิโอนี้ยังไม่มีโปรไฟล์",
                    "พอร์ตโฟลิโอจะว่างเปล่าจนกว่าจะมีโปรไฟล์ สร้างโปรไฟล์ก่อน",
                    ctx.urls["create_profile"], "สร้างโปรไฟล์")]


def check_template(ctx):
    if get_theme(ctx.portfolio.template_key) is not None:
        return []
    fallback = theme_for(ctx.portfolio)
    return [Finding(WARNING, "เทมเพลตที่เลือกไว้ไม่มีแล้ว",
                    f"ตอนนี้แสดงด้วยเทมเพลต {fallback.name} แทน เลือกเทมเพลตใหม่เพื่อให้แน่ใจว่าได้หน้าตาที่ต้องการ",
                    ctx.urls["version"], "เลือกเทมเพลต")]


def check_required_fields(ctx):
    if ctx.profile is None:
        return []
    return [
        Finding(WARNING, f"ยังไม่ได้กรอก{label}",
                "ผู้อ่านใช้ข้อมูลนี้เพื่อรู้ว่าคุณเป็นใครและติดต่อคุณได้อย่างไร",
                ctx.urls["profile"], "แก้ไขโปรไฟล์")
        for label in profile_missing_labels(ctx.profile)
    ]


def check_recommended_fields(ctx):
    profile = ctx.profile
    if profile is None:
        return []
    findings = []
    bio = (profile.bio or "").strip()
    if not bio:
        findings.append(Finding(INFO, "ยังไม่มีประวัติย่อ (About)",
                                "ประวัติย่อ 2–3 ประโยคช่วยให้ผู้อ่านเข้าใจภาพรวมของคุณเร็วขึ้น",
                                ctx.urls["profile"], "เพิ่มประวัติย่อ"))
    elif len(bio) > LONG_BIO:
        findings.append(Finding(INFO, "ประวัติย่อค่อนข้างยาว",
                                f"ยาว {len(bio)} ตัวอักษร อาจทำให้หน้าแรกของ PDF แน่นเกินไป "
                                f"ลองย่อให้เหลือไม่เกิน {LONG_BIO} ตัวอักษร",
                                ctx.urls["profile"], "แก้ประวัติย่อ"))
    if not profile.photo:
        findings.append(Finding(INFO, "ยังไม่มีรูปโปรไฟล์", "เทมเพลตจะแสดงอักษรย่อแทนรูป",
                                ctx.urls["profile"], "เพิ่มรูป"))
    if not (profile.location or "").strip():
        findings.append(Finding(INFO, "ยังไม่ได้ระบุที่อยู่หรือจังหวัด", "ช่วยให้ผู้รับสมัครรู้ว่าคุณอยู่ที่ไหน",
                                ctx.urls["profile"], "แก้ไขโปรไฟล์"))
    return findings


def check_photo_file(ctx):
    photo = ctx.profile.photo if ctx.profile is not None else None
    if photo and not photo.storage.exists(photo.name):
        return [Finding(WARNING, "ไม่พบไฟล์รูปโปรไฟล์",
                        "ระบบบันทึกชื่อรูปไว้แต่หาไฟล์ไม่เจอ รูปจะไม่แสดง ให้อัปโหลดรูปใหม่",
                        ctx.urls["profile"], "อัปโหลดรูปใหม่")]
    return []


def check_links(ctx):
    """Links that would be silently dropped from this version (only http/https are shown)."""
    profile = ctx.profile
    if profile is None:
        return []
    findings = []
    for name, label in (("website", "Website"), ("linkedin_url", "LinkedIn"), ("github_url", "GitHub")):
        if _is_bad_url(getattr(profile, name, "")):
            findings.append(Finding(ERROR, f"ลิงก์ {label} ไม่ถูกต้อง",
                                    "ใช้ได้เฉพาะลิงก์ที่ขึ้นต้นด้วย http:// หรือ https:// "
                                    "ลิงก์นี้จะไม่แสดงในพอร์ตโฟลิโอ",
                                    ctx.urls["profile"], "แก้ลิงก์"))
    shown = ctx.content.section("projects") if ctx.content else None
    shown_ids = {item.id for item in shown.items} if shown else set()
    for project in profile.projects.filter(pk__in=shown_ids):
        if _is_bad_url(project.project_url):
            findings.append(Finding(ERROR, f"ลิงก์ของโปรเจกต์ “{project.project_name}” ไม่ถูกต้อง",
                                    "ใช้ได้เฉพาะ http:// หรือ https:// ลิงก์นี้จะไม่แสดง",
                                    reverse("profiles:project_edit", args=[project.pk]), "แก้ลิงก์"))
    return findings


def check_removed_selection(ctx):
    """Items this version picked that were later deleted from the profile (they are skipped silently)."""
    if ctx.selected is None:
        return []
    from ..content_selection.sources import available_items  # local: FOLDO-06 imports our services
    from ..models import PortfolioContentSelection

    available = {key: {choice.id for choice in items} for key, items in available_items(ctx.portfolio).items()}
    gone = {}
    for row in PortfolioContentSelection.objects.filter(portfolio=ctx.portfolio):
        if row.item_id not in available.get(row.section, set()):
            gone[row.section] = gone.get(row.section, 0) + 1
    return [
        Finding(WARNING, f"ข้อมูลที่เลือกไว้ในส่วน{SECTION_TITLES_TH.get(key, key)}ถูกลบไปแล้ว",
                f"{count} รายการที่เคยเลือกไม่มีในโปรไฟล์แล้ว จึงไม่แสดง ตรวจการเลือกเนื้อหาอีกครั้ง",
                ctx.urls["content"], "ตรวจการเลือกเนื้อหา")
        for key, count in sorted(gone.items())
    ]


def check_sections(ctx):
    content = ctx.content
    if content is None or ctx.profile is None:
        return []
    if not content.sections and not content.profile.bio:
        return [Finding(ERROR, "พอร์ตโฟลิโอว่างเปล่า",
                        "ยังไม่มีประวัติย่อหรือเนื้อหาส่วนไหนเลย เพิ่มข้อมูลหรือเลือกเนื้อหาก่อนเผยแพร่หรือส่งออก",
                        ctx.urls["content"] or ctx.urls["profile"], "เลือกเนื้อหา")]
    present = {s.key for s in content.sections}
    findings = []
    for key, title in SECTION_TITLES_TH.items():
        if key in present:
            continue
        if ctx.selected is not None:
            # The owner chose this version's content: an empty section may be on purpose.
            findings.append(Finding(INFO, f"พอร์ตโฟลิโอนี้ไม่ได้เลือกส่วน{title}",
                                    "ส่วนนี้จะไม่แสดง ถ้างานที่สมัครต้องการ ให้เลือกเพิ่ม",
                                    ctx.urls["content"], "เลือกเนื้อหา"))
        else:
            findings.append(Finding(WARNING, f"ยังไม่มีข้อมูลส่วน{title}",
                                    "ส่วนนี้จะไม่แสดงในพอร์ตโฟลิโอ เพิ่มในโปรไฟล์ถ้างานที่สมัครต้องการ",
                                    ctx.urls.get(key, ""), f"เพิ่ม{title}"))
    return findings


def check_project_details(ctx):
    projects = ctx.content.section("projects") if ctx.content else None
    findings = []
    for item in projects.items if projects else ():
        fix = reverse("profiles:project_edit", args=[item.id])
        if not item.description:
            findings.append(Finding(INFO, f"โปรเจกต์ “{item.title}” ยังไม่มีคำอธิบาย",
                                    "เขียน 1–2 ประโยคว่าโปรเจกต์นี้คืออะไรและคุณทำส่วนไหน", fix, "เพิ่มคำอธิบาย"))
        labels = {label for label, _ in item.story}
        missing = [label for label in STORY_CORE if label not in labels]
        if item.story and missing:
            findings.append(Finding(INFO, f"Project Story ของ “{item.title}” ยังไม่ครบ",
                                    f"ยังขาด{', '.join(STORY_LABELS_TH.get(m, m) for m in missing)} "
                                    "เรื่องที่มีครบทั้งปัญหา บทบาท และผลลัพธ์จะน่าเชื่อถือกว่า",
                                    fix, "เติม Project Story"))
    return findings


def check_render(ctx):
    try:
        render_version_html(ctx.portfolio)
    except Exception:
        logger.exception("Quality check: rendering failed for portfolio %s", ctx.portfolio.pk)
        return [Finding(ERROR, f"แสดงผลด้วยเทมเพลต {theme_for(ctx.portfolio).name} ไม่สำเร็จ",
                        "ข้อมูลบางส่วนทำให้เทมเพลตนี้แสดงผลไม่ได้ ลองเปลี่ยนเทมเพลต หรือตรวจข้อมูลที่เพิ่งแก้ไข",
                        ctx.urls["version"], "เปลี่ยนเทมเพลต")]
    return []


CHECKS = (
    ("โปรไฟล์", check_profile_exists),
    ("เทมเพลต", check_template),
    ("ข้อมูลที่จำเป็น", check_required_fields),
    ("ข้อมูลที่แนะนำ", check_recommended_fields),
    ("รูปโปรไฟล์", check_photo_file),
    ("ลิงก์", check_links),
    ("เนื้อหาที่ถูกลบ", check_removed_selection),
    ("ส่วนเนื้อหา", check_sections),
    ("รายละเอียดผลงาน", check_project_details),
    ("การแสดงผล", check_render),
)


def run_quality_check(portfolio, *, checks=CHECKS) -> QualityReport:
    """Check one version as it will be shown. Read-only."""
    profile = resolve_profile(portfolio)
    selected = selected_ids(portfolio)
    ctx = CheckContext(portfolio=portfolio, profile=profile, selected=selected,
                       urls=_fix_urls(portfolio, profile))
    findings = []
    retry_url = reverse("portfolios:quality", args=[portfolio.pk])
    try:
        ctx.content = build_version_content(portfolio, selected=selected)
    except Exception:
        logger.exception("Quality check: reading content failed for portfolio %s", portfolio.pk)
        findings.append(Finding(ERROR, "อ่านข้อมูลของพอร์ตโฟลิโอนี้ไม่สำเร็จ",
                                "ข้อมูลของคุณยังอยู่ครบ ลองตรวจอีกครั้ง", retry_url, "ตรวจอีกครั้ง"))

    for name, check in checks:
        try:
            findings.extend(check(ctx))
        except Exception:
            logger.exception("Quality check '%s' failed for portfolio %s", name, portfolio.pk)
            findings.append(Finding(WARNING, f"ตรวจหัวข้อ “{name}” ไม่สำเร็จ",
                                    "ข้อนี้ตรวจไม่ได้ในครั้งนี้ ข้อมูลของคุณไม่ได้ถูกแก้ไข ลองตรวจอีกครั้ง",
                                    retry_url, "ตรวจอีกครั้ง"))

    order = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}
    findings.sort(key=lambda f: order[f.severity])
    return QualityReport(findings=tuple(findings), checked_at=timezone.now())
