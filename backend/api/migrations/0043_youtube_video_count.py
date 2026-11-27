from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0042_discovery_map_search"),
    ]

    operations = [
        migrations.AddField(
            model_name="youtubechannellink",
            name="video_count",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
