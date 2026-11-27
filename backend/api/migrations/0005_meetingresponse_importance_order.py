from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_meeting_phase1"),
    ]

    operations = [
        migrations.AddField(
            model_name="meetingresponse",
            name="importance_order",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Participant-ranked order on issue card slides (1 = highest importance).",
                null=True,
            ),
        ),
    ]
