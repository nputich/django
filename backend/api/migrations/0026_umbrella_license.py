import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0025_organization_relationship"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UmbrellaLicense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "max_members",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Blank = no cap on member organizations.",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="umbrella_license",
                        to="api.organization",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="organizationservice",
            name="billing_source",
            field=models.CharField(
                choices=[
                    ("FREE", "Free"),
                    ("PAYPAL", "PayPal"),
                    ("ACCESS_CODE", "Access code"),
                    ("ADMIN_GRANT", "Administrative grant"),
                    ("ENTERPRISE_CONTRACT", "Enterprise contract"),
                    ("UMBRELLA_LICENSE", "Umbrella license"),
                ],
                default="FREE",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="organizationservice",
            name="umbrella_license",
            field=models.ForeignKey(
                blank=True,
                help_text="Set when this entitlement is granted by another org's umbrella license.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="member_services",
                to="api.umbrellalicense",
            ),
        ),
    ]
