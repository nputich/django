# Generated manually for meeting wall lifecycle

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0018_wall_post_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="meeting",
            name="location",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="meeting",
            name="scheduled_end_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="meeting",
            name="results_visible_to_community",
            field=models.BooleanField(
                default=False,
                help_text="When True, eligible users may view meeting results after the meeting ends.",
            ),
        ),
        migrations.AddField(
            model_name="meeting",
            name="minutes_creator",
            field=models.CharField(
                choices=[
                    ("organizer_only", "Organizer only"),
                    ("organizer_or_attendees", "Organizer or attendees"),
                ],
                default="organizer_only",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="MeetingExpectedAttendance",
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
                (
                    "status",
                    models.CharField(
                        choices=[("going", "Going"), ("pending", "Pending")],
                        max_length=20,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "meeting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expected_attendances",
                        to="api.meeting",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meeting_expected_attendances",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="meetingexpectedattendance",
            constraint=models.UniqueConstraint(
                fields=("meeting", "user"),
                name="unique_meeting_expected_attendance_per_user",
            ),
        ),
        migrations.CreateModel(
            name="MeetingSummary",
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
                ("body", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Submitted"),
                            ("published", "Published"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("is_organizer_authored", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "meeting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="summaries",
                        to="api.meeting",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Meeting summaries",
                "ordering": ["-updated_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="boardpost",
            name="meeting",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="wall_post",
                to="api.meeting",
            ),
        ),
        migrations.AlterField(
            model_name="boardpost",
            name="post_type",
            field=models.CharField(
                choices=[
                    ("post", "Post"),
                    ("question", "Question"),
                    ("poll", "Poll"),
                    ("event", "Event"),
                    ("meeting", "Meeting"),
                ],
                default="post",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="personalboardpost",
            name="post_type",
            field=models.CharField(
                choices=[
                    ("post", "Post"),
                    ("question", "Question"),
                    ("poll", "Poll"),
                    ("event", "Event"),
                    ("meeting", "Meeting"),
                ],
                default="post",
                max_length=20,
            ),
        ),
    ]
