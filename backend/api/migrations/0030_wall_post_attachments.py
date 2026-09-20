from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0029_self_paced_content_survey_flow"),
    ]

    operations = [
        migrations.AddField(
            model_name="boardpost",
            name="attachment",
            field=models.FileField(
                blank=True, null=True, upload_to="wall_attachments/org/"
            ),
        ),
        migrations.AddField(
            model_name="boardpost",
            name="attachment_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="personalboardpost",
            name="attachment",
            field=models.FileField(
                blank=True, null=True, upload_to="wall_attachments/personal/"
            ),
        ),
        migrations.AddField(
            model_name="personalboardpost",
            name="attachment_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
