import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0024_starter_service_level"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationRelationship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("parent_child", "Parent / child"),
                            ("umbrella_member", "Umbrella license member"),
                            ("partner", "Partner"),
                            ("sponsor", "Sponsor"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("declined", "Declined"),
                            ("ended", "Ended"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=500)),
                (
                    "public",
                    models.BooleanField(
                        default=True,
                        help_text="Show this relationship on public hubs / directory.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="relationships",
                        to="api.conversation",
                    ),
                ),
                (
                    "ended_by_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="api.organization",
                    ),
                ),
                (
                    "from_organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relationships_from",
                        to="api.organization",
                    ),
                ),
                (
                    "initiated_by_organization",
                    models.ForeignKey(
                        help_text="Which side sent the request; the other side must accept.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relationships_initiated",
                        to="api.organization",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "responded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "to_organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relationships_to",
                        to="api.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["from_organization", "kind", "status"],
                        name="api_orgrel_from_kind_status",
                    ),
                    models.Index(
                        fields=["to_organization", "kind", "status"],
                        name="api_orgrel_to_kind_status",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("from_organization", models.F("to_organization")),
                            _negated=True,
                        ),
                        name="orgrel_no_self_relationship",
                    ),
                ],
            },
        ),
    ]
