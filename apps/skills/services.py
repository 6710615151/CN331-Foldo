"""
PLACEHOLDER for the Skills profile (one per user).

This file is the contract with the portfolios app. When you build the real module:

1. Add your model(s) (single record per user, e.g. a OneToOneField to the user) and migrations.
2. Replace the body of `get_skills_display` so it returns something template-friendly,
   or None when the user has no skills data yet. Never raise for missing data.
3. Render it in `templates/skills/_portfolio_section.html` (it receives `skills`).

portfolios only calls `get_skills_display(user)`; keep that name and signature,
and don't import from apps.portfolios (dependencies point one way).
"""
from __future__ import annotations


def get_skills_display(user):
    """Return render-safe skills data for `user`, or None. (Placeholder: always None.)"""
    return None
