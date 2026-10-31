"""
FOLDO-10: shared validation

Use these in forms.py / models.py instead of writing your own checks, so the
same rule applies everywhere.
"""

from django.core.validators import URLValidator

# Only normal web links (http / https). Use this on every field that stores a
safe_url_validator = URLValidator(schemes=["http", "https"])

# Maximum lengths (characters) shared by all apps.
MAX_SHORT_NAME = 100   # display name, skill name
MAX_SHORT_TEXT = 200   # project name, job title, institution
MAX_URL = 500          # any link
MAX_LONG_TEXT = 5000   # bio, description, project story