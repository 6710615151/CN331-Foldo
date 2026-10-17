"""
Business logic layer for the ``accounts`` app (mutations only).

Planned with the authentication Issue — e.g. ``register_user(...)`` wrapped in
``@transaction.atomic`` that creates the ``CustomUser`` (and, once the profiles
app exists, its empty profile) together. Views call these functions; they never
write to the database themselves.
"""
