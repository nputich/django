# Generated manually for YouTube channel location fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0043_youtube_video_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="youtubechannellink",
            name="state",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="youtubechannellink",
            name="zip_code",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="youtubechannellink",
            name="lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="youtubechannellink",
            name="lng",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="youtubechannellink",
            name="tags",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="User-defined tags for this channel (Map Search).",
            ),
        ),
    ]
