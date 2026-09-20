# Generated manually — optional blank organization board titles

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0019_meeting_wall_lifecycle"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organizationboard",
            name="title",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
