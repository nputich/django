from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_boardpostreply"),
    ]

    operations = [
        migrations.RenameField(
            model_name="meetingresponse",
            old_name="response_text",
            new_name="raw_response",
        ),
        migrations.RenameField(
            model_name="meetingresponse",
            old_name="normalized_text",
            new_name="normalized_response",
        ),
        migrations.RemoveField(
            model_name="meetingresponse",
            name="raw_text",
        ),
        migrations.RenameField(
            model_name="politicalclassification",
            old_name="major_issue_bucket",
            new_name="major_issue",
        ),
        migrations.RenameField(
            model_name="politicalclassification",
            old_name="specific_issue_bucket",
            new_name="specific_issue",
        ),
        migrations.RemoveField(
            model_name="politicalclassification",
            name="concern_bucket",
        ),
    ]
