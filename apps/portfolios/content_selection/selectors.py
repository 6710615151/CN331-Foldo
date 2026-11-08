"""Read side of content selection (FOLDO-06)."""
from __future__ import annotations

from ..models import PortfolioContentSelection, PortfolioContentSetup
from .sources import SECTION_KEYS, available_items


def is_customised(portfolio) -> bool:
    return PortfolioContentSetup.objects.filter(portfolio=portfolio).exists()


def get_selected_ids(portfolio) -> dict[str, set[int]] | None:
    """
    ``{section: {ids}}`` for this version, or ``None`` when it was never customised
    (meaning "show everything"). Ids whose source row no longer exists are dropped.
    """
    if not is_customised(portfolio):
        return None
    chosen = {key: set() for key in SECTION_KEYS}
    for row in PortfolioContentSelection.objects.filter(portfolio=portfolio):
        if row.section in chosen:
            chosen[row.section].add(row.item_id)
    available = available_items(portfolio)
    return {key: chosen[key] & {c.id for c in available[key]} for key in SECTION_KEYS}


def selection_state(portfolio) -> dict[str, set[int]]:
    """What the selection page shows as ticked (everything, if never customised)."""
    selected = get_selected_ids(portfolio)
    if selected is None:
        return {key: {c.id for c in items} for key, items in available_items(portfolio).items()}
    return selected
