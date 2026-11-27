from django.db import migrations, models
import django.db.models.deletion


def seed_measure_reading(apps, schema_editor):
    PluginDefinition = apps.get_model("api", "PluginDefinition")
    PluginDefinition.objects.get_or_create(
        key="measure_reading",
        defaults={
            "name": "Measure Reading",
            "description": (
                "Load a House or Senate source into a measure, edit it before voting, "
                "and review each invited member's revisions."
            ),
            "enabled": True,
            "audience": "organization",
            "requires_approval": False,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0052_legislative_bill"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Measure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(default="ncga", max_length=32)),
                ("external_key", models.CharField(blank=True, max_length=64)),
                ("session_year", models.PositiveIntegerField(blank=True, null=True)),
                ("bill_type", models.CharField(blank=True, max_length=12)),
                ("bill_number", models.PositiveIntegerField(blank=True, null=True)),
                ("title", models.CharField(blank=True, max_length=300)),
                ("body", models.TextField(blank=True)),
                ("summary", models.TextField(blank=True)),
                ("source_url", models.URLField(blank=True, max_length=500)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("voting", "Voting")], default="draft", max_length=16)),
                ("passage_percent", models.PositiveSmallIntegerField(default=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="auth.user")),
                ("install", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="measures", to="api.plugininstall")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="measures", to="api.organization")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="MeasureMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(blank=True, max_length=80)),
                ("color_index", models.PositiveSmallIntegerField(default=0)),
                ("measure", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="api.measure")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="measure_seats", to="auth.user")),
            ],
        ),
        migrations.AddConstraint(
            model_name="measuremember",
            constraint=models.UniqueConstraint(fields=("measure", "user"), name="uniq_measure_member"),
        ),
        migrations.CreateModel(
            name="MeasureRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("measure", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="api.measure")),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="api.measuremember")),
            ],
        ),
        migrations.AddConstraint(
            model_name="measurerevision",
            constraint=models.UniqueConstraint(fields=("measure", "member"), name="uniq_measure_revision"),
        ),
        migrations.RunPython(seed_measure_reading, migrations.RunPython.noop),
    ]
