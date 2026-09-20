# Generated manually for self-paced meetings, content slides, and survey flow.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0028_seed_question_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="meeting",
            name="allow_self_paced",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When True, participants may answer any slide without waiting for the "
                    "organizer to advance. Default is organizer-paced."
                ),
            ),
        ),
        migrations.AddField(
            model_name="survey",
            name="aggregate_sharing_notice",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Tell respondents that anonymous combined results may be shared with "
                    "policymakers and decision makers not listed in the disclosure."
                ),
            ),
        ),
        migrations.AddField(
            model_name="surveyquestion",
            name="is_demographic",
            field=models.BooleanField(
                default=False,
                help_text="Demographic questions are shown after the main survey questions.",
            ),
        ),
        migrations.AddField(
            model_name="surveyquestion",
            name="config",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="For content blocks: body, banner_url, video_url.",
            ),
        ),
        migrations.AlterField(
            model_name="surveyquestion",
            name="text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="surveyquestion",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("choice", "Multiple choice"),
                    ("content", "Content (text / media)"),
                ],
                default="text",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="meetingslide",
            name="slide_type",
            field=models.CharField(
                choices=[
                    ("participant_info", "Participant information"),
                    ("content", "Content (text / media)"),
                    ("standard", "Standard question"),
                    ("issue_card", "Issue card"),
                    ("political_issue_card", "Political issue card"),
                ],
                max_length=30,
            ),
        ),
    ]
