from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0051_voter_file_label"),
    ]

    operations = [
        migrations.CreateModel(
            name="LegislativeBill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_year", models.PositiveIntegerField(db_index=True)),
                ("bill_type", models.CharField(db_index=True, max_length=12)),
                ("bill_number", models.PositiveIntegerField()),
                ("chamber", models.CharField(choices=[("house", "House"), ("senate", "Senate")], max_length=12)),
                ("title", models.TextField(blank=True)),
                ("introduced_date", models.DateField(blank=True, null=True)),
                ("latest_action", models.TextField(blank=True)),
                ("latest_action_date", models.DateField(blank=True, null=True)),
                ("official_summary", models.TextField(blank=True)),
                ("bill_text", models.TextField(blank=True)),
                ("source_url", models.URLField(blank=True, max_length=500)),
                ("analysis_summary", models.TextField(blank=True)),
                ("analysis", models.JSONField(blank=True, default=dict)),
                ("analysis_status", models.CharField(choices=[("pending", "Pending"), ("done", "Done"), ("failed", "Failed")], default="pending", max_length=16)),
                ("analysis_error", models.TextField(blank=True)),
                ("analysis_model", models.CharField(blank=True, max_length=80)),
                ("analyzed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-latest_action_date", "-bill_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="legislativebill",
            constraint=models.UniqueConstraint(fields=("session_year", "bill_type", "bill_number"), name="uniq_legislative_bill"),
        ),
    ]
