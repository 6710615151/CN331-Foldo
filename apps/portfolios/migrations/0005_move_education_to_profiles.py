"""Move per-user education (the retired ``apps.education``) into ``profiles.Education``.

Education now belongs to a Main Profile, like skills, experience and projects
(ER table PROFILE_EDUCATIONS). Each old ``education_educationentry`` row is copied
to its owner's default profile (or their first profile), and every portfolio
selection that pointed at the old row is pointed at the new one, so nobody loses
what they picked. Users with no profile have nowhere to show education, so their
old rows are dropped.

The old app is no longer installed, so its table is read with plain SQL (fixed
statements, no user input) and dropped at the end. On a database that never had
the table, this migration does nothing.

It lives in ``portfolios`` because it touches both apps' tables.
"""

import datetime

from django.db import migrations

OLD_TABLE = "education_educationentry"
LEVEL_LABELS = {
    "high_school": "High school",
    "undergraduate": "Undergraduate degree",
    "graduate": "Graduate degree (Master's)",
    "phd": "PhD",
}


def _year(value):
    return datetime.date(int(value), 1, 1) if value else None


def forwards(apps, schema_editor):
    connection = schema_editor.connection
    if OLD_TABLE not in connection.introspection.table_names():
        return

    MainProfile = apps.get_model("profiles", "MainProfile")
    Education = apps.get_model("profiles", "Education")
    Selection = apps.get_model("portfolios", "PortfolioContentSelection")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, owner_id, level, institution, subject, grade, start_year, end_year, created_at "
            f"FROM {OLD_TABLE} ORDER BY id"
        )
        rows = cursor.fetchall()

    new_ids = {}
    for old_id, owner_id, level, institution, subject, grade, start_year, end_year, created_at in rows:
        if not any((institution, subject, grade, start_year, end_year)):
            continue  # a level with nothing filled in was never shown
        profile = (
            MainProfile.objects.filter(owner_id=owner_id).order_by("-is_default", "pk").first()
        )
        if profile is None:
            continue
        start = _year(start_year) or _year(end_year)
        if start is None:
            start = created_at.date() if hasattr(created_at, "date") else datetime.date.today()
        end = _year(end_year)
        if end is not None and end < start:
            end = None
        label = LEVEL_LABELS.get(level, "")
        education = Education.objects.create(
            profile=profile,
            institution=(institution or label or "Education")[:200],
            degree=label[:200],
            field_of_study=(subject or "")[:200],
            start_date=start,
            end_date=end,
            grade=(grade or "")[:50],
        )
        new_ids[old_id] = education.pk

    # Point saved selections at the new rows; drop ones whose source did not move.
    for selection in Selection.objects.filter(section="education"):
        new_id = new_ids.get(selection.item_id)
        if new_id is None:
            selection.delete()
        elif not Selection.objects.filter(
            portfolio_id=selection.portfolio_id, section="education", item_id=new_id
        ).exclude(pk=selection.pk).exists():
            selection.item_id = new_id
            selection.save(update_fields=["item_id"])
        else:
            selection.delete()

    schema_editor.execute(f"DROP TABLE {OLD_TABLE}")


class Migration(migrations.Migration):

    dependencies = [
        ("portfolios", "0004_content_selection"),
        ("profiles", "0006_education"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
