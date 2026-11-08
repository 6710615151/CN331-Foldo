"""The portfolio templates users can choose from (FOLDO-07).

Templates live in code, not in a table: each one is a Django template file plus
CSS, so adding a row without the file would break rendering. A portfolio
version (FOLDO-05) stores the theme's ``key``; validate it with ``get_theme()``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioTheme:
    key: str
    name: str
    description: str
    category: str

    @property
    def template_name(self) -> str:
        return f"rendering/themes/{self.key}.html"


THEMES = (
    PortfolioTheme(
        key="classic",
        name="Classic",
        description="หนึ่งคอลัมน์ อ่านง่าย เหมาะกับงานสายวิชาการและราชการ",
        category="University",
    ),
    PortfolioTheme(
        key="modern",
        name="Modern",
        description="สองคอลัมน์ มีแถบข้างสำหรับข้อมูลติดต่อและทักษะ เหมาะกับสายเทค",
        category="Career",
    ),
    PortfolioTheme(
        key="creative",
        name="Creative",
        description="หัวกระดาษสีเด่น ผลงานเป็นการ์ด เหมาะกับสายออกแบบและฟรีแลนซ์",
        category="Creative",
    ),
)

DEFAULT_THEME_KEY = "classic"

_BY_KEY = {theme.key: theme for theme in THEMES}


def get_theme(key: str) -> PortfolioTheme | None:
    return _BY_KEY.get(key)


def resolve_theme(key: str | None) -> PortfolioTheme:
    """The theme for a stored key; an unknown or retired key falls back to the
    default, so a saved portfolio always renders."""
    return _BY_KEY.get(key or "", _BY_KEY[DEFAULT_THEME_KEY])


def theme_choices() -> list[tuple[str, str]]:
    """For a ``CharField(choices=...)`` on PortfolioVersion."""
    return [(theme.key, theme.name) for theme in THEMES]
