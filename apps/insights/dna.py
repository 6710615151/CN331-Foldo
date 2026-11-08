"""Portfolio DNA (FOLDO-14): which portfolio versions reuse each profile item.

``build_dna`` is a pure read. It never changes selections or source items, so
viewing DNA can't delete anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from .sources import SourceItem, VersionRef, portfolio_versions, source_sections


@dataclass(frozen=True)
class DnaRow:
    item: SourceItem
    used_in: tuple[VersionRef, ...]

    @property
    def is_unused(self) -> bool:
        return not self.used_in


@dataclass(frozen=True)
class DnaSection:
    key: str
    title: str
    rows: tuple[DnaRow, ...]


@dataclass(frozen=True)
class MissingSelection:
    """A version still points at an item that no longer exists."""

    version: VersionRef
    section: str
    item_id: int


@dataclass(frozen=True)
class DnaReport:
    sections: tuple[DnaSection, ...]
    versions: tuple[VersionRef, ...]
    missing: tuple[MissingSelection, ...]

    @property
    def rows(self) -> list[DnaRow]:
        return [row for section in self.sections for row in section.rows]

    @property
    def total_items(self) -> int:
        return len(self.rows)

    @property
    def unused_items(self) -> list[DnaRow]:
        return [row for row in self.rows if row.is_unused]

    @property
    def reused_items(self) -> list[DnaRow]:
        return [row for row in self.rows if len(row.used_in) > 1]


def compute_dna(sections, versions) -> DnaReport:
    """``sections``: (key, title, [SourceItem]); ``versions``: [VersionRef]."""
    known: set[tuple[str, int]] = set()
    dna_sections = []
    for key, title, items in sections:
        rows = []
        for item in items:
            known.add((key, item.id))
            rows.append(DnaRow(item=item, used_in=tuple(v for v in versions if v.uses(key, item.id))))
        dna_sections.append(DnaSection(key=key, title=title, rows=tuple(rows)))

    missing = tuple(
        MissingSelection(version=version, section=section, item_id=item_id)
        for version in versions
        for section, ids in sorted(version.selected.items())
        for item_id in sorted(ids)
        if (section, item_id) not in known
    )
    return DnaReport(sections=tuple(dna_sections), versions=tuple(versions), missing=missing)


def build_dna(profile, *, providers=None, versions=None) -> DnaReport:
    return compute_dna(
        source_sections(profile, providers),
        portfolio_versions(profile) if versions is None else versions,
    )
