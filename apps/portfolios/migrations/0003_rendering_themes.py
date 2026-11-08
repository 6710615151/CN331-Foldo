"""FOLDO-07: portfolio versions use the apps.rendering templates.

The four colour variants of one layout (classic / midnight / ocean / mono) are
replaced by three distinct layouts (classic / modern / creative). Existing rows
are moved to the closest new template so nothing breaks or silently resets.
"""

from django.db import migrations, models

# Old key -> new key. "classic" keeps its key but now uses the rendering layout.
LEGACY_TO_THEME = {
    "classic": "classic",
    "midnight": "modern",   # dark sidebar
    "ocean": "creative",    # bold blue header
    "mono": "classic",      # plain, single column
}
VALID = {"classic", "modern", "creative"}


def forwards(apps, schema_editor):
    Portfolio = apps.get_model("portfolios", "Portfolio")
    for old, new in LEGACY_TO_THEME.items():
        if old != new:
            Portfolio.objects.filter(template_key=old).update(template_key=new)
    Portfolio.objects.exclude(template_key__in=VALID).update(template_key="classic")


class Migration(migrations.Migration):

    dependencies = [
        ("portfolios", "0002_alter_portfolio_template_key"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="portfolio",
            name="template_key",
            field=models.CharField(
                choices=[("classic", "Classic"), ("modern", "Modern"), ("creative", "Creative")],
                default="classic",
                max_length=40,
            ),
        ),
    ]
