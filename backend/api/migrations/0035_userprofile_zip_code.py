from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0034_organization_wall_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="zip_code",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
