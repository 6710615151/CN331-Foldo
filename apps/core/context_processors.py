"""
Template context for the signed-in app shell (sidebar + top bar).

``shell`` is ``None`` for visitors. For a signed-in user it is an ``AppShell``
whose properties are computed lazily and cached, so a page that never renders
the shell (the public portfolio, the PDF source) never runs these queries.
Every read is scoped to ``request.user``.
"""

from functools import cached_property

from django.db import DatabaseError

# url_name prefix -> sidebar section, for views inside apps.profiles
_PROFILE_SECTIONS = (
    ("education", "education"),
    ("skill", "skills"),
    ("experience", "skills"),
    ("project", "projects"),
)

SECTION_LABELS = {
    "dashboard": "แดชบอร์ด",
    "onboarding": "เริ่มต้นใช้งาน",
    "profile": "โปรไฟล์",
    "education": "การศึกษา",
    "skills": "ทักษะและประสบการณ์",
    "projects": "โปรเจกต์",
    "portfolios": "พอร์ตโฟลิโอ",
    "templates": "เทมเพลต",
    "settings": "บัญชี",
}


class AppShell:
    def __init__(self, request):
        self.request = request
        self.user = request.user

    # --- navigation ------------------------------------------------------
    @cached_property
    def section(self) -> str:
        """Which sidebar item is the current page (drives the active state)."""
        match = getattr(self.request, "resolver_match", None)
        if match is None:
            return ""
        app, name = match.app_name, match.url_name or ""
        if app == "core":
            return name  # "dashboard" / "onboarding"
        if app == "profiles":
            for prefix, section in _PROFILE_SECTIONS:
                if name.startswith(prefix):
                    return section
            return "profile"
        if app == "portfolios":
            return "portfolios"
        if app == "rendering":
            return "templates"
        if app == "accounts":
            return "settings"
        return ""

    @property
    def section_label(self) -> str:
        return SECTION_LABELS.get(self.section, "")

    # --- the user's data (lazy) -----------------------------------------
    @cached_property
    def profile(self):
        from apps.profiles.services import get_default_profile

        try:
            return get_default_profile(self.user)
        except DatabaseError:  # the shell must never take a page down
            return None

    @cached_property
    def display_name(self) -> str:
        if self.profile and self.profile.full_name.strip():
            return self.profile.full_name.strip()
        return self.user.get_full_name() or self.user.get_username()

    @cached_property
    def initials(self) -> str:
        parts = self.display_name.split()[:2]
        return "".join(part[0] for part in parts).upper() or "?"

    @cached_property
    def photo_url(self) -> str:
        try:
            return self.profile.photo.url if self.profile and self.profile.photo else ""
        except ValueError:
            return ""

    @cached_property
    def nav_profile(self):
        """The profile the sidebar's Education / Skills / Projects links point at.

        On a page that belongs to one of the user's profiles (that profile, or a
        row inside it) it is *that* profile, so the links never jump to another
        one; everywhere else it is the default profile.
        """
        match = getattr(self.request, "resolver_match", None)
        if match is not None and match.app_name == "profiles":
            try:
                found = _profile_for_route(self.user, match.url_name or "", match.kwargs)
            except DatabaseError:
                found = None
            if found is not None:
                return found
        return self.profile

    @cached_property
    def profile_count(self) -> int:
        from apps.profiles.services import get_profiles

        try:
            return get_profiles(self.user).count()
        except DatabaseError:
            return 0

    @cached_property
    def todos(self) -> list[dict]:
        """Real, actionable reminders shown under the bell icon (required steps only)."""
        from apps.core.selectors import get_next_steps

        try:
            return get_next_steps(self.user, include_recommended=False, profile=self.profile)
        except DatabaseError:
            return []


def _profile_for_route(user, url_name, kwargs):
    """The owned profile a /profiles/ route is about, or None."""
    from apps.profiles.models import Education, Experience, Project, Skill
    from apps.profiles.services import get_profile

    if "profile_pk" in kwargs:
        return get_profile(user, kwargs["profile_pk"])
    pk = kwargs.get("pk")
    if pk is None:
        return None
    if url_name in ("view", "update", "delete", "make_default"):
        return get_profile(user, pk)
    for prefix, model in (("education", Education), ("skill", Skill), ("experience", Experience), ("project", Project)):
        if url_name.startswith(prefix):
            profile_id = model.objects.filter(pk=pk, profile__owner=user).values_list("profile_id", flat=True).first()
            return get_profile(user, profile_id) if profile_id else None
    return None


def shell(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"shell": None}
    return {"shell": AppShell(request)}
