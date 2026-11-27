from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0037_profile_field_visibility"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="show_memberships_on_profile",
            field=models.BooleanField(
                default=False,
                help_text="List organization memberships on the public profile.",
            ),
        ),
        migrations.AddField(
            model_name="organizationmembership",
            name="show_on_profile",
            field=models.BooleanField(
                default=True,
                help_text="Show this membership on the member's public profile when enabled.",
            ),
        ),
    ]
