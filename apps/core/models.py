"""
Models for the ``core`` app.

``core`` intentionally owns **no** database models: it provides the shared
shell (base template, navigation, landing page and health check) that the
other apps build on. Adding a model here without a matching backlog Issue
would be premature.

Shared, reusable utilities belong in ``services.py`` when they become genuinely
necessary.
"""
