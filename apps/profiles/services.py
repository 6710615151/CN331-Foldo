"""
Public interface of the profiles module.

Other apps (portfolio versions, exports, ...) should import from here, never touch
MainProfile fields directly. `get_profile_display` never raises for missing data and
always returns a fully populated structure, so templates need no defensive logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import MainProfile


@dataclass(frozen=True)
class ContactItem:
    label: str
    value: str
    href: str = ""


@dataclass(frozen=True)
class ProfileDisplay:
    exists: bool
    display_name: str
    headline: str = ""
    bio: str = ""
    location: str = ""
    photo_url: str = ""
    contacts: list[ContactItem] = field(default_factory=list)
    links: list[ContactItem] = field(default_factory=list)
    is_complete: bool = False
    missing_fields: list[str] = field(default_factory=list)

    @property
    def initials(self) -> str:
        parts = self.display_name.split()[:2]
        return "".join(p[0] for p in parts).upper() or "?"


def get_profile(user) -> MainProfile | None:
    """Return the user's own profile, or None. Anonymous users never get one."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return MainProfile.objects.filter(owner=user).first()


def get_or_create_profile(user) -> MainProfile:
    profile = get_profile(user)
    if profile is None:
        profile = MainProfile.objects.create(owner=user, full_name=user.get_username())
    return profile


def _photo_url(profile: MainProfile) -> str:
    try:
        return profile.photo.url if profile.photo else ""
    except ValueError:
        return ""


def build_display(user, profile: MainProfile | None = None) -> ProfileDisplay:
    """Render-safe view of a profile; pass `profile` to skip a query if you already have it."""
    if profile is None:
        profile = get_profile(user)

    fallback_name = user.get_username() if getattr(user, "is_authenticated", False) else ""
    if profile is None:
        return ProfileDisplay(
            exists=False,
            display_name=fallback_name,
            missing_fields=list(MainProfile.REQUIRED_FOR_PORTFOLIO.values()),
        )

    contacts = []
    if profile.contact_email:
        contacts.append(ContactItem("Email", profile.contact_email, f"mailto:{profile.contact_email}"))
    if profile.phone:
        tel = "".join(ch for ch in profile.phone if ch.isdigit() or ch == "+")
        contacts.append(ContactItem("Phone", profile.phone, f"tel:{tel}" if tel else ""))

    links = [
        ContactItem(label, url, url)
        for label, url in (
            ("Website", profile.website),
            ("LinkedIn", profile.linkedin_url),
            ("GitHub", profile.github_url),
        )
        if url
    ]

    return ProfileDisplay(
        exists=True,
        display_name=profile.full_name.strip() or fallback_name,
        headline=profile.headline,
        bio=profile.bio,
        location=profile.location,
        photo_url=_photo_url(profile),
        contacts=contacts,
        links=links,
        is_complete=profile.is_complete,
        missing_fields=profile.missing_fields,
    )


# Convenience alias for other modules.
get_profile_display = build_display
