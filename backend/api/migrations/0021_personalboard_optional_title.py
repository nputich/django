# Generated manually — optional blank personal board titles

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0020_organizationboard_optional_title"),
    ]

    operations = [
        migrations.AlterField(
            model_name="personalboard",
            name="title",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
