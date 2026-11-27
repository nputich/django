# Generated manually — plan usage periods, survey submissions, session attendee cap

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0022_organizationboard_hub_preview_count"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationUsagePeriod",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("period_start", models.DateTimeField(db_index=True)),
                ("period_end", models.DateTimeField()),
                ("service_level", models.CharField(max_length=32)),
                ("survey_submissions_used", models.PositiveIntegerField(default=0)),
                ("meetings_started_used", models.PositiveIntegerField(default=0)),
                ("ai_meeting_runs_used", models.PositiveIntegerField(default=0)),
                ("board_posts_used", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_periods",
                        to="api.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-period_start", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="organizationusageperiod",
            constraint=models.UniqueConstraint(
                fields=("organization", "period_start"),
                name="uniq_org_usage_period_start",
            ),
        ),
        migrations.AddIndex(
            model_name="organizationusageperiod",
            index=models.Index(
                fields=["organization", "-period_start"],
                name="api_organiz_organiz_usage_idx",
            ),
        ),
        migrations.CreateModel(
            name="AiUsageEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(blank=True, default="", max_length=32)),
                ("consumed_run", models.BooleanField(default=False)),
                ("success", models.BooleanField(default=True)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "meeting",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_usage_events",
                        to="api.meeting",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_usage_events",
                        to="api.organization",
                    ),
                ),
                (
                    "usage_period",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_usage_events",
                        to="api.organizationusageperiod",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="aiusageevent",
            index=models.Index(
                fields=["usage_period", "meeting"],
                name="api_aiusage_period_mtg_idx",
            ),
        ),
        migrations.CreateModel(
            name="SurveySubmission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("response_session", models.CharField(db_index=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="survey_submissions",
                        to="api.organization",
                    ),
                ),
                (
                    "survey",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submissions",
                        to="api.survey",
                    ),
                ),
                (
                    "usage_period",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="survey_submissions",
                        to="api.organizationusageperiod",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="surveysubmission",
            constraint=models.UniqueConstraint(
                fields=("survey", "response_session"),
                name="uniq_survey_response_session",
            ),
        ),
        migrations.AddIndex(
            model_name="surveysubmission",
            index=models.Index(
                fields=["organization", "usage_period"],
                name="api_surveys_organiz_period_idx",
            ),
        ),
        migrations.AddField(
            model_name="meetingsession",
            name="attendee_limit",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Snapshot of plan interactive-attendee cap when the session went live.",
                null=True,
            ),
        ),
    ]
