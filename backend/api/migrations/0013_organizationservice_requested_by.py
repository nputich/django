# Generated manually for OrganizationService.requested_by

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0012_organization_service"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationservice",
            name="requested_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who started this checkout or entitlement request.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="requested_organization_services",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
