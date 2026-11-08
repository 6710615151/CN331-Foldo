"""Reading the selection page's POST (FOLDO-06). Anything not offered to the owner is ignored later."""
from __future__ import annotations

from .sources import SECTION_KEYS


def parse_selection(data) -> dict[str, set[int]]:
    """``data`` is ``request.POST``; each section is a list of checked item ids. Junk is skipped."""
    chosen: dict[str, set[int]] = {}
    for key in SECTION_KEYS:
        ids = set()
        for raw in data.getlist(key):
            try:
                ids.add(int(raw))
            except (TypeError, ValueError):
                continue
        chosen[key] = ids
    return chosen
