from django.db import migrations


_LEGACY = {
    "hidden_to_public": "private",
    "org_only": "org_admins",
    "hidden_all": "private",
}


def _rewrite_map(raw):
    if not isinstance(raw, dict):
        return {}, False
    changed = False
    out = {}
    for key, value in raw.items():
        if key == "username":
            if value != "public":
                changed = True
            out[key] = "public"
            continue
        mapped = _LEGACY.get(value, value)
        if mapped != value:
            changed = True
        out[key] = mapped
    return out, changed


def rewrite_visibility(apps, schema_editor):
    UserProfile = apps.get_model("api", "UserProfile")
    Organization = apps.get_model("api", "Organization")
    OrganizationMembership = apps.get_model("api", "OrganizationMembership")

    for model in (UserProfile, Organization, OrganizationMembership):
        for row in model.objects.all().iterator():
            rewritten, changed = _rewrite_map(getattr(row, "field_visibility", None))
            if changed:
                row.field_visibility = rewritten
                row.save(update_fields=["field_visibility"])


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0040_control_numbers"),
    ]

    operations = [
        migrations.RunPython(rewrite_visibility, migrations.RunPython.noop),
    ]
