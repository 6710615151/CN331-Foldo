"""
PLACEHOLDER for the Education profile (one per user).

This file is the contract with the portfolios app. When you build the real module:

1. Add your model(s) (single record per user, e.g. a OneToOneField to the user) and migrations.
2. Replace the body of `get_education_display` so it returns something template-friendly,
   or None when the user has no education data yet. Never raise for missing data.
3. Render it in `templates/education/_portfolio_section.html` (it receives `education`).

portfolios only calls `get_education_display(user)`; keep that name and signature,
and don't import from apps.portfolios (dependencies point one way).
"""
from __future__ import annotations


def get_education_display(user):
    """Return render-safe education data for `user`, or None. (Placeholder: always None.)"""
    return None
