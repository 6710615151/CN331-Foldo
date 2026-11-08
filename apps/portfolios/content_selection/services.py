"""Write side of content selection (FOLDO-06). Never touches source profile data."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.db import transaction

from ..models import PortfolioContentSelection, PortfolioContentSetup
from .sources import SECTION_KEYS, available_items


@transaction.atomic
def save_selection(portfolio, chosen: Mapping[str, Iterable[int]]) -> int:
    """
    Replace this version's selection with ``chosen``; return how many submitted ids were
    ignored because they are not available to the owner (deleted, or someone else's).

    Only this portfolio's selection rows change: other versions and the source
    profile data are untouched.
    """
    available = {key: {c.id for c in items} for key, items in available_items(portfolio).items()}
    rows, ignored = [], 0
    for key in SECTION_KEYS:
        wanted = {int(i) for i in chosen.get(key, ())}
        valid = wanted & available[key]
        ignored += len(wanted - valid)
        rows.extend(
            PortfolioContentSelection(portfolio=portfolio, section=key, item_id=item_id)
            for item_id in sorted(valid)
        )
    PortfolioContentSelection.objects.filter(portfolio=portfolio).delete()
    PortfolioContentSelection.objects.bulk_create(rows)
    setup, _ = PortfolioContentSetup.objects.get_or_create(portfolio=portfolio)
    setup.save()  # bump updated_at even when the rows are unchanged
    return ignored


@transaction.atomic
def reset_selection(portfolio) -> None:
    """Back to "show everything" (the version is no longer customised)."""
    PortfolioContentSelection.objects.filter(portfolio=portfolio).delete()
    PortfolioContentSetup.objects.filter(portfolio=portfolio).delete()
