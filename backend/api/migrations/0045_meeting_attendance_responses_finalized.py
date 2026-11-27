from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0044_youtube_channel_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="meetingattendance",
            name="responses_finalized_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Self-paced meetings: participant confirmed all answers are final.",
                null=True,
            ),
        ),
    ]
