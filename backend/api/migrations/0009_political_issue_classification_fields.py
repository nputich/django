from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_political_response_field_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="meetingresponse",
            name="major_issue",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="specific_issue",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="issue_type",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="classification_confidence",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="classification_status",
            field=models.CharField(default="pending", max_length=20),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="review_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="classified_raw_snapshot",
            field=models.TextField(
                blank=True,
                help_text="Raw response text at the last political classification run.",
            ),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="classification_reprocess",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="meetingresponse",
            name="classification_processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
