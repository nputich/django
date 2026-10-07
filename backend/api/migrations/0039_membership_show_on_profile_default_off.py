from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0038_profile_membership_visibility"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organizationmembership",
            name="show_on_profile",
            field=models.BooleanField(
                default=False,
                help_text="Show this membership on the member's public profile.",
            ),
        ),
        # Existing rows created with the old default=True should start hidden.
        migrations.RunSQL(
            sql="UPDATE api_organizationmembership SET show_on_profile = FALSE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
