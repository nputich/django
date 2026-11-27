from django.db import migrations


def seed_map_search(apps, schema_editor):
    PluginDefinition = apps.get_model("api", "PluginDefinition")
    PluginDefinition.objects.get_or_create(
        key="map_search",
        defaults={
            "name": "Map Search",
            "description": "Find member channels by tag and location for this organization.",
            "enabled": True,
            "audience": "organization",
            "requires_approval": False,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0048_plugin_access_approval"),
    ]

    operations = [
        migrations.RunPython(seed_map_search, migrations.RunPython.noop),
    ]
