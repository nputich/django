from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0045_meeting_attendance_responses_finalized"),
    ]

    operations = [
        migrations.AddField(
            model_name="meeting",
            name="live_results_for_participants",
            field=models.BooleanField(
                default=False,
                help_text="Participants may view combined results for slides the organizer releases during the meeting.",
            ),
        ),
        migrations.AddField(
            model_name="meetingsession",
            name="participant_results_released_slide_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Slide IDs whose combined results participants may view in this session.",
            ),
        ),
        migrations.AddField(
            model_name="survey",
            name="live_results_for_respondents",
            field=models.BooleanField(
                default=False,
                help_text="Respondents may view combined results for questions the organizer releases.",
            ),
        ),
        migrations.AddField(
            model_name="survey",
            name="participant_results_released_question_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Survey question IDs whose combined results respondents may view.",
            ),
        ),
    ]
