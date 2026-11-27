from django.db import migrations, models


def create_sequences_and_backfill(apps, schema_editor):
    UserProfile = apps.get_model("api", "UserProfile")
    Organization = apps.get_model("api", "Organization")

    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "CREATE SEQUENCE IF NOT EXISTS communibetter_user_control_number_seq "
                "OWNED BY NONE START WITH 1 INCREMENT BY 1"
            )
            cursor.execute(
                "CREATE SEQUENCE IF NOT EXISTS communibetter_org_control_number_seq "
                "OWNED BY NONE START WITH 1 INCREMENT BY 1"
            )
            for profile in UserProfile.objects.filter(control_number__isnull=True).order_by(
                "id"
            ):
                cursor.execute(
                    "SELECT nextval('communibetter_user_control_number_seq')"
                )
                n = cursor.fetchone()[0]
                UserProfile.objects.filter(pk=profile.pk).update(control_number=n)
            for org in Organization.objects.filter(control_number__isnull=True).order_by(
                "id"
            ):
                cursor.execute(
                    "SELECT nextval('communibetter_org_control_number_seq')"
                )
                n = cursor.fetchone()[0]
                Organization.objects.filter(pk=org.pk).update(control_number=n)
    else:
        # SQLite / tests: simple incremental assign.
        n = 1
        for profile in UserProfile.objects.filter(control_number__isnull=True).order_by(
            "id"
        ):
            UserProfile.objects.filter(pk=profile.pk).update(control_number=n)
            n += 1
        n = 1
        for org in Organization.objects.filter(control_number__isnull=True).order_by("id"):
            Organization.objects.filter(pk=org.pk).update(control_number=n)
            n += 1


def drop_sequences(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "DROP SEQUENCE IF EXISTS communibetter_user_control_number_seq"
            )
            cursor.execute(
                "DROP SEQUENCE IF EXISTS communibetter_org_control_number_seq"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0039_membership_show_on_profile_default_off"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="control_number",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                editable=False,
                help_text="Stable CommuniBetter member ID (displayed as U-<n>).",
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="control_number",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                editable=False,
                help_text="Stable CommuniBetter organization ID (displayed as O-<n>).",
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(create_sequences_and_backfill, drop_sequences),
    ]
