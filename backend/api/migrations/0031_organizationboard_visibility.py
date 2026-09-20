from django.db import migrations, models


def seed_visibility_from_posting_mode(apps, schema_editor):
    OrganizationBoard = apps.get_model("api", "OrganizationBoard")
    for board in OrganizationBoard.objects.all().iterator():
        # Restricted used to be publicly readable; treat as members-only visibility.
        if board.posting_mode == "public":
            board.visibility = "public"
        elif board.posting_mode == "members_only":
            board.visibility = "members_only"
        else:
            board.visibility = "members_only"
        board.save(update_fields=["visibility"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0030_wall_post_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationboard",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("public", "Public"),
                    ("members_only", "Members only"),
                    ("private", "Private (admins only)"),
                ],
                default="public",
                help_text="Who can see posts on this wall (hub preview only when Public).",
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_visibility_from_posting_mode, migrations.RunPython.noop),
    ]
