import django.contrib.auth.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0031_organizationboard_visibility"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrgDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=255)),
                ("original_name", models.CharField(max_length=255)),
                ("file", models.FileField(upload_to="org_documents/%Y/%m/")),
                ("content_type", models.CharField(blank=True, default="", max_length=128)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                (
                    "visibility",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("private", "Private"),
                            ("restricted", "Restricted"),
                        ],
                        default="private",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="api.organization",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="uploaded_org_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="DocumentShareList",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
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
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_share_lists",
                        to="api.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="DocumentShareListMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "share_list",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="api.documentsharelist",
                    ),
                ),
                (
                    "shared_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="api.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OrgDocumentShare",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("revoked", "Revoked")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shares",
                        to="api.orgdocument",
                    ),
                ),
                (
                    "share_list",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_shares",
                        to="api.documentsharelist",
                    ),
                ),
                (
                    "shared_organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents_shared_with_us",
                        to="api.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_shares_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="orgdocument",
            index=models.Index(
                fields=["organization", "visibility", "-created_at"],
                name="api_orgdocu_organiz_7e8c1a_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentsharelist",
            constraint=models.UniqueConstraint(
                fields=("organization", "name"),
                name="uniq_document_share_list_name_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentsharelistmember",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("shared_organization__isnull", True), ("user__isnull", False))
                    | models.Q(("shared_organization__isnull", False), ("user__isnull", True))
                ),
                name="document_share_list_member_one_target",
            ),
        ),
        migrations.AddIndex(
            model_name="orgdocumentshare",
            index=models.Index(fields=["document", "status"], name="api_orgdocu_documen_8f2b4c_idx"),
        ),
        migrations.AddConstraint(
            model_name="orgdocumentshare",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        ("share_list__isnull", True),
                        ("shared_organization__isnull", True),
                        ("user__isnull", False),
                    )
                    | models.Q(
                        ("share_list__isnull", True),
                        ("shared_organization__isnull", False),
                        ("user__isnull", True),
                    )
                    | models.Q(
                        ("share_list__isnull", False),
                        ("shared_organization__isnull", True),
                        ("user__isnull", True),
                    )
                ),
                name="org_document_share_one_target",
            ),
        ),
    ]
