from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_nc_plugin(apps, schema_editor):
    PluginDefinition = apps.get_model("api", "PluginDefinition")
    PluginDefinition.objects.get_or_create(
        key="nc_voter_powerquery",
        defaults={
            "name": "NC Voter Record PowerQuery",
            "description": (
                "Upload a North Carolina voter file, compare it with another file "
                "or the official Communibetter copy, and query the rows."
            ),
            "enabled": True,
            "audience": "both",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0046_live_participant_results"),
    ]

    operations = [
        migrations.CreateModel(
            name="PluginDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("enabled", models.BooleanField(default=True)),
                (
                    "audience",
                    models.CharField(
                        choices=[
                            ("personal", "Personal"),
                            ("organization", "Organization"),
                            ("both", "Personal and organization"),
                        ],
                        default="both",
                        max_length=20,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PluginInstall",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("installed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "installed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plugin_installs",
                        to="api.organization",
                    ),
                ),
                (
                    "plugin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="installs",
                        to="api.plugindefinition",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plugin_installs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="plugininstall",
            constraint=models.CheckConstraint(
                condition=models.Q(user__isnull=False, organization__isnull=True)
                | models.Q(user__isnull=True, organization__isnull=False),
                name="plugin_install_one_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="plugininstall",
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=False),
                fields=("plugin", "user"),
                name="plugin_install_unique_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="plugininstall",
            constraint=models.UniqueConstraint(
                condition=models.Q(organization__isnull=False),
                fields=("plugin", "organization"),
                name="plugin_install_unique_org",
            ),
        ),
        migrations.CreateModel(
            name="VoterFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("owner_upload", "Owner upload"),
                            ("official", "Official"),
                            ("comparison_list", "Comparison list"),
                        ],
                        max_length=32,
                    ),
                ),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                ("stored_path", models.CharField(blank=True, max_length=500)),
                ("row_count", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("parsing", "Parsing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("error", models.TextField(blank=True)),
                ("parsed_at", models.DateTimeField(blank=True, null=True)),
                ("is_current_official", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "install",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="voter_files",
                        to="api.plugininstall",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="voterfile",
            index=models.Index(fields=["install", "source", "status"], name="api_voterfi_install_8a0c0d_idx"),
        ),
        migrations.AddIndex(
            model_name="voterfile",
            index=models.Index(fields=["is_current_official"], name="api_voterfi_is_curr_6b1e2a_idx"),
        ),
        migrations.CreateModel(
            name="VoterRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("county", models.CharField(blank=True, db_index=True, max_length=80)),
                ("county_id", models.CharField(blank=True, max_length=16)),
                ("ncid", models.CharField(blank=True, db_index=True, max_length=32)),
                ("last_name", models.CharField(blank=True, max_length=80)),
                ("first_name", models.CharField(blank=True, max_length=80)),
                ("middle_name", models.CharField(blank=True, max_length=80)),
                ("address", models.CharField(blank=True, max_length=200)),
                ("city", models.CharField(blank=True, max_length=80)),
                ("zip_code", models.CharField(blank=True, max_length=16)),
                ("status", models.CharField(blank=True, max_length=40)),
                ("party", models.CharField(blank=True, max_length=16)),
                ("line_hash", models.CharField(blank=True, max_length=64)),
                (
                    "voter_file",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="records",
                        to="api.voterfile",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="voterrecord",
            index=models.Index(fields=["voter_file", "ncid"], name="api_voterre_voter_f_ncid_idx"),
        ),
        migrations.AddIndex(
            model_name="voterrecord",
            index=models.Index(fields=["voter_file", "county"], name="api_voterre_voter_f_county_idx"),
        ),
        migrations.RunPython(seed_nc_plugin, migrations.RunPython.noop),
    ]
