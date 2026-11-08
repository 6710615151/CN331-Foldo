"""Data access for education (pure reads). Callers pass a profile they already own."""


def get_educations(profile):
    return profile.educations.all()
