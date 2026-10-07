from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0033_orgdocument_index_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="profile_picture",
            field=models.ImageField(
                blank=True, null=True, upload_to="org_profiles/"
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="public_username",
            field=models.SlugField(
                blank=True,
                default="",
                help_text="Public @handle for the organization wall. Blank until set.",
                max_length=50,
            ),
        ),
    ]
