from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0036_organization_contact_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="first_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="field_visibility",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="organization",
            name="first_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="organization",
            name="last_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="organization",
            name="field_visibility",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="organizationmembership",
            name="shared_profile",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="organizationmembership",
            name="field_visibility",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
