# Generated manually for locality area type support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_geographic_directory"),
    ]

    operations = [
        migrations.AlterField(
            model_name="geographicarea",
            name="area_type",
            field=models.CharField(
                choices=[
                    ("country", "Country"),
                    ("admin1", "State / Province / Territory"),
                    ("admin2", "County / County-equivalent"),
                    ("locality", "City / Locality"),
                    ("region", "Regional area"),
                ],
                max_length=20,
            ),
        ),
    ]
