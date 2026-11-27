"""Organization documents with Public / Private / Restricted ACLs."""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from api.board_service import is_org_admin, is_org_member
from api.models import (
    DocumentShareList,
    DocumentShareListMember,
    OrgDocument,
    OrgDocumentShare,
    Organization,
    OrganizationMembership,
)

# Hard limits for organization documents (v1).
DOCUMENT_ALLOWED_EXTENSIONS = frozenset(
    {
        # Documents
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Pictures
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
)
DOCUMENT_ALLOWED_LABEL = (
    "PDF, Word, Excel, PowerPoint, and pictures (PNG, JPG, GIF, WebP)"
)
DOCUMENT_MAX_BYTES = 15 * 1024 * 1024  # 15 MB


class DocumentError(ValueError):
    def __init__(self, message: str, *, code: str = "document_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def document_limits_payload() -> dict:
    return {
        "max_bytes": DOCUMENT_MAX_BYTES,
        "max_mb": DOCUMENT_MAX_BYTES // (1024 * 1024),
        "allowed_extensions": sorted(DOCUMENT_ALLOWED_EXTENSIONS),
        "allowed_label": DOCUMENT_ALLOWED_LABEL,
    }


def validate_document_file(uploaded) -> None:
    if uploaded is None:
        raise ValidationError({"file": "Choose a file to upload."})
    name = getattr(uploaded, "name", "") or ""
    ext = Path(name).suffix.lower()
    if ext not in DOCUMENT_ALLOWED_EXTENSIONS:
        raise ValidationError(
            {
                "file": f"Allowed types: {DOCUMENT_ALLOWED_LABEL}."
            }
        )
    size = getattr(uploaded, "size", None)
    if size is not None and size > DOCUMENT_MAX_BYTES:
        mb = DOCUMENT_MAX_BYTES // (1024 * 1024)
        raise ValidationError({"file": f"File must be {mb} MB or smaller."})


def can_manage_document(document: OrgDocument, user: User | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if document.uploaded_by_id == user.id:
        return True
    return is_org_admin(document.organization, user)


def _user_in_share_list(share_list: DocumentShareList, user: User) -> bool:
    if DocumentShareListMember.objects.filter(share_list=share_list, user=user).exists():
        return True
    member_org_ids = OrganizationMembership.objects.filter(user=user).values_list(
        "organization_id", flat=True
    )
    return DocumentShareListMember.objects.filter(
        share_list=share_list, shared_organization_id__in=member_org_ids
    ).exists()


def can_access_document(document: OrgDocument, user: User | None) -> bool:
    if document.visibility == OrgDocument.Visibility.PUBLIC:
        return True
    if not user or not user.is_authenticated:
        return False
    if document.uploaded_by_id == user.id:
        return True
    if is_org_admin(document.organization, user):
        return True
    if document.visibility == OrgDocument.Visibility.PRIVATE:
        return False

    # Restricted: explicit shares
    if OrgDocumentShare.objects.filter(
        document=document, status=OrgDocumentShare.Status.ACTIVE, user=user
    ).exists():
        return True

    user_org_ids = list(
        OrganizationMembership.objects.filter(user=user).values_list(
            "organization_id", flat=True
        )
    )
    if user_org_ids and OrgDocumentShare.objects.filter(
        document=document,
        status=OrgDocumentShare.Status.ACTIVE,
        shared_organization_id__in=user_org_ids,
    ).exists():
        return True

    list_ids = OrgDocumentShare.objects.filter(
        document=document,
        status=OrgDocumentShare.Status.ACTIVE,
        share_list__isnull=False,
    ).values_list("share_list_id", flat=True)
    for list_id in list_ids:
        share_list = DocumentShareList.objects.filter(pk=list_id).first()
        if share_list and _user_in_share_list(share_list, user):
            return True
    return False


def documents_visible_to_user(organization: Organization, user: User):
    qs = OrgDocument.objects.filter(organization=organization).select_related(
        "uploaded_by", "uploaded_by__profile"
    )
    if is_org_admin(organization, user):
        return qs
    # Uploader, public, or shared to me / my orgs / my lists
    user_org_ids = list(
        OrganizationMembership.objects.filter(user=user).values_list(
            "organization_id", flat=True
        )
    )
    shared_doc_ids = OrgDocumentShare.objects.filter(
        status=OrgDocumentShare.Status.ACTIVE
    ).filter(
        Q(user=user)
        | Q(shared_organization_id__in=user_org_ids)
        | Q(
            share_list__members__user=user
        )
        | Q(share_list__members__shared_organization_id__in=user_org_ids)
    ).values_list("document_id", flat=True)

    return qs.filter(
        Q(visibility=OrgDocument.Visibility.PUBLIC)
        | Q(uploaded_by=user)
        | Q(id__in=shared_doc_ids)
    ).distinct()


@transaction.atomic
def create_document(
    *,
    organization: Organization,
    user: User,
    uploaded,
    title: str = "",
    visibility: str = OrgDocument.Visibility.PRIVATE,
) -> OrgDocument:
    validate_document_file(uploaded)
    vis = (visibility or OrgDocument.Visibility.PRIVATE).strip().lower()
    if vis not in {c.value for c in OrgDocument.Visibility}:
        raise DocumentError("Invalid visibility.", code="invalid_visibility")
    original = Path(getattr(uploaded, "name", "") or "document").name[:255]
    doc = OrgDocument(
        organization=organization,
        uploaded_by=user,
        title=(title or "").strip()[:255] or Path(original).stem[:255],
        original_name=original,
        visibility=vis,
        content_type=getattr(uploaded, "content_type", "") or "",
        size_bytes=getattr(uploaded, "size", 0) or 0,
    )
    doc.file = uploaded
    doc.save()
    return doc


def set_visibility(document: OrgDocument, visibility: str, user: User) -> OrgDocument:
    if not can_manage_document(document, user):
        raise DocumentError("Not allowed.", code="forbidden")
    vis = (visibility or "").strip().lower()
    if vis not in {c.value for c in OrgDocument.Visibility}:
        raise DocumentError("Invalid visibility.", code="invalid_visibility")
    document.visibility = vis
    document.save(update_fields=["visibility", "updated_at"])
    return document


def _activate_or_create_share(document: OrgDocument, actor: User, **target_fields) -> OrgDocumentShare:
    if document.visibility == OrgDocument.Visibility.PRIVATE:
        document.visibility = OrgDocument.Visibility.RESTRICTED
        document.save(update_fields=["visibility", "updated_at"])
    existing = (
        OrgDocumentShare.objects.filter(document=document, **target_fields)
        .order_by("id")
        .first()
    )
    if existing:
        if existing.status != OrgDocumentShare.Status.ACTIVE:
            existing.status = OrgDocumentShare.Status.ACTIVE
            existing.revoked_at = None
            existing.created_by = actor
            existing.save(update_fields=["status", "revoked_at", "created_by"])
        return existing
    return OrgDocumentShare.objects.create(
        document=document,
        created_by=actor,
        status=OrgDocumentShare.Status.ACTIVE,
        **target_fields,
    )


def grant_user_share(document: OrgDocument, *, target: User, actor: User) -> OrgDocumentShare:
    if not can_manage_document(document, actor):
        raise DocumentError("Not allowed.", code="forbidden")
    return _activate_or_create_share(
        document,
        actor,
        user=target,
        shared_organization=None,
        share_list=None,
    )


def grant_org_share(
    document: OrgDocument, *, target: Organization, actor: User
) -> OrgDocumentShare:
    if not can_manage_document(document, actor):
        raise DocumentError("Not allowed.", code="forbidden")
    if target.id == document.organization_id:
        raise DocumentError("Cannot share with the owning organization.", code="invalid_target")
    return _activate_or_create_share(
        document,
        actor,
        user=None,
        shared_organization=target,
        share_list=None,
    )


def grant_list_share(
    document: OrgDocument, *, share_list: DocumentShareList, actor: User
) -> OrgDocumentShare:
    if not can_manage_document(document, actor):
        raise DocumentError("Not allowed.", code="forbidden")
    if share_list.organization_id != document.organization_id:
        raise DocumentError("That list belongs to another organization.", code="invalid_target")
    return _activate_or_create_share(
        document,
        actor,
        user=None,
        shared_organization=None,
        share_list=share_list,
    )


def revoke_share(share: OrgDocumentShare, actor: User) -> None:
    if not can_manage_document(share.document, actor):
        raise DocumentError("Not allowed.", code="forbidden")
    if share.status == OrgDocumentShare.Status.REVOKED:
        return
    share.status = OrgDocumentShare.Status.REVOKED
    share.revoked_at = timezone.now()
    share.save(update_fields=["status", "revoked_at"])


@transaction.atomic
def create_share_list(
    *, organization: Organization, user: User, name: str
) -> DocumentShareList:
    cleaned = (name or "").strip()[:120]
    if not cleaned:
        raise DocumentError("List name is required.", code="invalid_name")
    if DocumentShareList.objects.filter(organization=organization, name__iexact=cleaned).exists():
        raise DocumentError("A list with that name already exists.", code="duplicate_name")
    return DocumentShareList.objects.create(
        organization=organization, name=cleaned, created_by=user
    )


def add_list_member(
    share_list: DocumentShareList,
    *,
    actor: User,
    user: User | None = None,
    organization: Organization | None = None,
) -> DocumentShareListMember:
    if not is_org_admin(share_list.organization, actor) and share_list.created_by_id != getattr(
        actor, "id", None
    ):
        # Allow org members who manage docs to edit lists in their org
        if not is_org_member(share_list.organization, actor):
            raise DocumentError("Not allowed.", code="forbidden")
    if bool(user) == bool(organization):
        raise DocumentError("Provide a person or an organization.", code="invalid_target")
    member, _ = DocumentShareListMember.objects.get_or_create(
        share_list=share_list,
        user=user,
        shared_organization=organization,
    )
    return member


def remove_list_member(member: DocumentShareListMember, actor: User) -> None:
    org = member.share_list.organization
    if not is_org_member(org, actor):
        raise DocumentError("Not allowed.", code="forbidden")
    member.delete()


def serialize_share(share: OrgDocumentShare) -> dict:
    payload = {
        "id": share.id,
        "status": share.status,
        "created_at": share.created_at,
        "kind": None,
        "label": "",
    }
    if share.user_id:
        profile = getattr(share.user, "profile", None)
        payload["kind"] = "user"
        payload["username"] = share.user.username
        payload["label"] = (profile.display_name if profile and profile.display_name else "") or share.user.username
        payload["user_id"] = share.user_id
    elif share.shared_organization_id:
        payload["kind"] = "organization"
        payload["organization_slug"] = share.shared_organization.slug
        payload["label"] = share.shared_organization.name
        payload["organization_id"] = share.shared_organization_id
    elif share.share_list_id:
        payload["kind"] = "list"
        payload["share_list_id"] = share.share_list_id
        payload["label"] = share.share_list.name
    return payload


def serialize_document(document: OrgDocument, request, *, include_shares: bool = False) -> dict:
    from django.urls import reverse

    can_manage = can_manage_document(document, request.user if request else None)
    download_path = reverse(
        "org-document-download",
        kwargs={"slug": document.organization.slug, "pk": document.id},
    )
    payload = {
        "id": document.id,
        "title": document.title,
        "original_name": document.original_name,
        "visibility": document.visibility,
        "visibility_label": document.get_visibility_display(),
        "size_bytes": document.size_bytes,
        "content_type": document.content_type,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "uploaded_by": {
            "id": document.uploaded_by_id,
            "username": document.uploaded_by.username,
            "display_name": getattr(
                getattr(document.uploaded_by, "profile", None), "display_name", ""
            )
            or document.uploaded_by.username,
        },
        "can_manage": can_manage,
        "download_url": request.build_absolute_uri(download_path) if request else download_path,
    }
    if include_shares:
        shares = (
            document.shares.filter(status=OrgDocumentShare.Status.ACTIVE)
            .select_related("user__profile", "shared_organization", "share_list")
            .order_by("id")
        )
        payload["shares"] = [serialize_share(s) for s in shares]
    return payload


def serialize_share_list(share_list: DocumentShareList) -> dict:
    members = share_list.members.select_related("user__profile", "shared_organization")
    member_payload = []
    for m in members:
        if m.user_id:
            profile = getattr(m.user, "profile", None)
            member_payload.append(
                {
                    "id": m.id,
                    "kind": "user",
                    "user_id": m.user_id,
                    "username": m.user.username,
                    "label": (profile.display_name if profile and profile.display_name else "")
                    or m.user.username,
                }
            )
        else:
            member_payload.append(
                {
                    "id": m.id,
                    "kind": "organization",
                    "organization_id": m.shared_organization_id,
                    "organization_slug": m.shared_organization.slug,
                    "label": m.shared_organization.name,
                }
            )
    return {
        "id": share_list.id,
        "name": share_list.name,
        "members": member_payload,
        "created_at": share_list.created_at,
    }
