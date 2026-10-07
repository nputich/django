from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0035_userprofile_zip_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="organization",
            name="contact_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="organization",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="organization",
            name="state",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="organization",
            name="zip_code",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
