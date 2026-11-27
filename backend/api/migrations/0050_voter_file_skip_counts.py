from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0049_map_search_plugin"),
    ]

    operations = [
        migrations.AddField(
            model_name="voterfile",
            name="rows_skipped",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="voterfile",
            name="skip_samples",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
