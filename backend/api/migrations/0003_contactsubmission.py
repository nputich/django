from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_meeting_organization_resourcetype_meetingquestion_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=200)),
                ("message", models.TextField(max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
