"""Read-only queries for projects (FOLDO-04)."""


def get_projects(profile):
    """All projects on one profile, newest first (see Project.Meta.ordering)."""
    return profile.projects.all()