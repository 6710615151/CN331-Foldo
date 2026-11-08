"""Data access for skills and experience (pure reads). Callers pass a profile they already own."""


def get_skills(profile):
    return profile.skills.all()


def get_experiences(profile):
    return profile.experiences.all()
