from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0050_voter_file_skip_counts"),
    ]

    operations = [
        migrations.AddField(
            model_name="voterfile",
            name="label",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
