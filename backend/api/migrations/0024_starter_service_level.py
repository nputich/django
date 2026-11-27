from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0023_plan_usage_limits"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accesscoderedemption",
            name="service_level",
            field=models.CharField(
                choices=[
                    ("FREE", "Organization (Free)"),
                    ("STARTER", "Starter"),
                    ("BASIC", "Basic"),
                    ("COMMUNITY", "Community"),
                    ("COMMUNITY_PLUS", "Community Plus"),
                    ("ENTERPRISE", "Enterprise"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="organizationservice",
            name="service_level",
            field=models.CharField(
                choices=[
                    ("FREE", "Organization (Free)"),
                    ("STARTER", "Starter"),
                    ("BASIC", "Basic"),
                    ("COMMUNITY", "Community"),
                    ("COMMUNITY_PLUS", "Community Plus"),
                    ("ENTERPRISE", "Enterprise"),
                ],
                max_length=32,
            ),
        ),
    ]
