from django.db import migrations, models
import django.db.models.deletion


STREAMERS_FIELDS = [
    {
        "key": "topics",
        "label": "Topics",
        "type": "multi_select",
        "required": True,
        "searchable": True,
        "options": [
            {"value": "politics", "label": "Politics"},
            {"value": "fashion", "label": "Fashion"},
            {"value": "blog", "label": "Blog"},
            {"value": "gaming", "label": "Gaming"},
            {"value": "tech", "label": "Tech"},
            {"value": "news", "label": "News"},
            {"value": "lifestyle", "label": "Lifestyle"},
            {"value": "other", "label": "Other"},
        ],
    },
    {
        "key": "state",
        "label": "State",
        "type": "text",
        "required": True,
        "searchable": True,
    },
    {
        "key": "zip_code",
        "label": "ZIP",
        "type": "text",
        "required": False,
        "searchable": True,
    },
]


def seed_streamers_international(apps, schema_editor):
    Organization = apps.get_model("api", "Organization")
    org, _ = Organization.objects.get_or_create(
        slug="streamers-international",
        defaults={
            "name": "Streamers International",
            "description": (
                "A global community for streamers to find each other by topic and location."
            ),
            "geographic_scope": "international",
            "discovery_enabled": True,
            "discovery_fields": STREAMERS_FIELDS,
            "is_verified": True,
            "is_active": True,
            "status": "active",
        },
    )
    updates = []
    if not org.discovery_enabled:
        org.discovery_enabled = True
        updates.append("discovery_enabled")
    if not org.discovery_fields:
        org.discovery_fields = STREAMERS_FIELDS
        updates.append("discovery_fields")
    if org.name != "Streamers International":
        org.name = "Streamers International"
        updates.append("name")
    if updates:
        org.save(update_fields=updates)


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0041_visibility_public_org_admins_private"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="discovery_enabled",
            field=models.BooleanField(
                default=False,
                help_text="When True, members can use Map Search for this organization.",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="discovery_fields",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Org-defined discovery schema: [{key,label,type,required,searchable,options?}].",
            ),
        ),
        migrations.AddField(
            model_name="organizationmembership",
            name="discovery_lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="organizationmembership",
            name="discovery_lng",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="organizationmembership",
            name="discovery_listed",
            field=models.BooleanField(
                default=False,
                help_text="When True, this member appears on the org Map Search map/list.",
            ),
        ),
        migrations.CreateModel(
            name="YouTubeChannelLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("channel_id", models.CharField(db_index=True, max_length=64)),
                ("title", models.CharField(blank=True, default="", max_length=255)),
                (
                    "custom_url",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("thumbnail_url", models.URLField(blank=True, default="")),
                ("subscriber_count", models.BigIntegerField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(auto_now_add=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("refresh_token", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="youtube_channels",
                        to="auth.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-subscriber_count", "title"],
                "unique_together": {("user", "channel_id")},
            },
        ),
        migrations.RunPython(seed_streamers_international, migrations.RunPython.noop),
    ]
