from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def mark_communibetter(apps, schema_editor):
    Organization = apps.get_model("api", "Organization")
    PluginDefinition = apps.get_model("api", "PluginDefinition")
    PluginDefinition.objects.filter(key="nc_voter_powerquery").update(requires_approval=True)
    for org in Organization.objects.filter(slug__startswith="communibetter-"):
        org.is_communibetter = True
        if org.slug == "communibetter-united-states" and not org.geographic_scope:
            org.geographic_scope = "national"
        elif org.slug == "communibetter-north-carolina" and not org.geographic_scope:
            org.geographic_scope = "state_province"
        org.save(update_fields=["is_communibetter", "geographic_scope"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0047_plugin_warehouse"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="is_communibetter",
            field=models.BooleanField(
                default=False,
                help_text="Official Communibetter organization. State and national ones can approve voter-plugin access.",
            ),
        ),
        migrations.AddField(
            model_name="plugindefinition",
            name="requires_approval",
            field=models.BooleanField(
                default=False,
                help_text="Install stays pending until a Communibetter state or national admin approves it.",
            ),
        ),
        migrations.AddField(
            model_name="plugininstall",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("denied", "Denied"),
                ],
                default="approved",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="plugininstall",
            name="request_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="plugininstall",
            name="decision_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="plugininstall",
            name="decided_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="plugininstall",
            name="decided_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(mark_communibetter, migrations.RunPython.noop),
    ]
