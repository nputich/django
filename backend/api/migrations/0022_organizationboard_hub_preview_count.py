# Generated manually — org hub board preview count

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0021_personalboard_optional_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationboard",
            name="hub_preview_count",
            field=models.PositiveSmallIntegerField(
                default=5,
                help_text="How many newest board posts to show on the public organization hub (0 hides the preview).",
            ),
        ),
    ]
