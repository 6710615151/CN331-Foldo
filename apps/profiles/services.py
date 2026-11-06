"""
Public interface of the profiles module.

Other apps (portfolio versions, exports, ...) should import from here, never touch
MainProfile fields directly. `build_display` never raises for missing data and
always returns a fully populated structure, so templates need no defensive logic.

Every lookup is scoped to the given user, so one user can never read another's profile.
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


def _is_authenticated(user) -> bool:
    return user is not None and getattr(user, "is_authenticated", False)


def get_profiles(user):
    """All of this user's profiles (default first). Empty for anonymous users."""
    if not _is_authenticated(user):
        return MainProfile.objects.none()
    return MainProfile.objects.filter(owner=user)


def get_default_profile(user) -> MainProfile | None:
    profiles = get_profiles(user)
    # Falls back to the most recently updated one if no row is flagged as default.
    return profiles.filter(is_default=True).first() or profiles.order_by("-updated_at").first()


def get_profile(user, pk=None) -> MainProfile | None:
    """The user's profile with this id, or their default when pk is None. None if not theirs."""
    if pk is None:
        return get_default_profile(user)
    return get_profiles(user).filter(pk=pk).first()


def get_or_create_profile(user) -> MainProfile:
    profile = get_default_profile(user)
    if profile is None:
        profile = MainProfile.objects.create(owner=user, full_name=user.get_username())
    return profile


def set_default_profile(profile: MainProfile) -> None:
    profile.is_default = True
    profile.save(update_fields=["is_default"])


def _photo_url(profile: MainProfile) -> str:
    try:
        return profile.photo.url if profile.photo else ""
    except ValueError:
        return ""


def build_display(user, profile: MainProfile | None = None) -> ProfileDisplay:
    """Render-safe view of a profile. Without `profile`, the user's default is used."""
    if profile is None:
        profile = get_default_profile(user)

    fallback_name = user.get_username() if _is_authenticated(user) else ""
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
