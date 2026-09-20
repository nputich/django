"""Organization document library API."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.board_service import is_org_member
from api.document_service import (
    DocumentError,
    add_list_member,
    can_access_document,
    can_manage_document,
    create_document,
    create_share_list,
    document_limits_payload,
    documents_visible_to_user,
    grant_list_share,
    grant_org_share,
    grant_user_share,
    remove_list_member,
    revoke_share,
    serialize_document,
    serialize_share_list,
    set_visibility,
)
from api.models import (
    DocumentShareList,
    DocumentShareListMember,
    OrgDocument,
    OrgDocumentShare,
    Organization,
)



def _member_org(request, slug):
    org = Organization.objects.filter(slug=slug, is_active=True).first()
    if not org or not is_org_member(org, request.user):
        return None, Response(
            {"detail": "Organization not found or you are not a member."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return org, None


def _error(exc: DocumentError):
    http = status.HTTP_400_BAD_REQUEST
    if exc.code == "forbidden":
        http = status.HTTP_403_FORBIDDEN
    if exc.code in ("duplicate_name",):
        http = status.HTTP_409_CONFLICT
    return Response({"detail": exc.message, "code": exc.code}, status=http)


class UserLookupView(APIView):
    """Typeahead for sharing documents with people."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response({"results": []})
        users = (
            User.objects.filter(is_active=True)
            .filter(Q(username__icontains=q) | Q(profile__display_name__icontains=q))
            .select_related("profile")
            .order_by("username")[:12]
        )
        results = []
        for u in users:
            profile = getattr(u, "profile", None)
            results.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "display_name": (profile.display_name if profile else "") or u.username,
                }
            )
        return Response({"results": results})


class OrganizationDocumentListView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, slug):
        org, err = _member_org(request, slug)
        if err:
            return err
        docs = documents_visible_to_user(org, request.user)
        return Response(
            {
                "organization_slug": org.slug,
                "limits": document_limits_payload(),
                "can_upload": is_org_member(org, request.user),
                "documents": [
                    serialize_document(d, request, include_shares=False) for d in docs
                ],
            }
        )

    def post(self, request, slug):
        org, err = _member_org(request, slug)
        if err:
            return err
        uploaded = request.FILES.get("file")
        title = request.data.get("title") or ""
        visibility = request.data.get("visibility") or OrgDocument.Visibility.PRIVATE
        try:
            doc = create_document(
                organization=org,
                user=request.user,
                uploaded=uploaded,
                title=title,
                visibility=visibility,
            )
        except DocumentError as exc:
            return _error(exc)
        except ValidationError as exc:
            detail = exc.detail
            if isinstance(detail, dict) and "file" in detail:
                msg = detail["file"]
                if isinstance(msg, list):
                    msg = msg[0]
                return Response({"detail": str(msg), "code": "invalid_file"}, status=400)
            raise
        doc = OrgDocument.objects.select_related("uploaded_by__profile", "organization").get(
            pk=doc.pk
        )
        return Response(
            serialize_document(doc, request, include_shares=True),
            status=status.HTTP_201_CREATED,
        )


class OrganizationDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        org, err = _member_org(request, slug)
        if err:
            return err
        doc = get_object_or_404(
            OrgDocument.objects.select_related("uploaded_by__profile", "organization"),
            pk=pk,
            organization=org,
        )
        if not can_access_document(doc, request.user):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_document(doc, request, include_shares=can_manage_document(doc, request.user)))

    def patch(self, request, slug, pk):
        org, err = _member_org(request, slug)
        if err:
            return err
        doc = get_object_or_404(OrgDocument, pk=pk, organization=org)
        try:
            if "visibility" in request.data:
                set_visibility(doc, request.data.get("visibility"), request.user)
            if "title" in request.data and can_manage_document(doc, request.user):
                doc.title = (request.data.get("title") or "").strip()[:255]
                doc.save(update_fields=["title", "updated_at"])
            elif "title" in request.data:
                raise DocumentError("Not allowed.", code="forbidden")
        except DocumentError as exc:
            return _error(exc)
        doc.refresh_from_db()
        return Response(serialize_document(doc, request, include_shares=True))

    def delete(self, request, slug, pk):
        org, err = _member_org(request, slug)
        if err:
            return err
        doc = get_object_or_404(OrgDocument, pk=pk, organization=org)
        if not can_manage_document(doc, request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        if doc.file:
            doc.file.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationDocumentDownloadView(APIView):
    """ACL-checked download (public docs allow anonymous)."""

    permission_classes = [AllowAny]

    def get(self, request, slug, pk):
        org = get_object_or_404(Organization, slug=slug, is_active=True)
        doc = get_object_or_404(OrgDocument, pk=pk, organization=org)
        user = request.user if request.user.is_authenticated else None
        if not can_access_document(doc, user):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not doc.file:
            return Response({"detail": "File missing."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(
            doc.file.open("rb"),
            as_attachment=True,
            filename=doc.original_name or doc.title or "document",
        )


class OrganizationDocumentSharesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        org, err = _member_org(request, slug)
        if err:
            return err
        doc = get_object_or_404(OrgDocument, pk=pk, organization=org)
        if not can_manage_document(doc, request.user):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        return Response(serialize_document(doc, request, include_shares=True))

    def post(self, request, slug, pk):
        org, err = _member_org(request, slug)
        if err:
            return err
        doc = get_object_or_404(OrgDocument, pk=pk, organization=org)
        kind = (request.data.get("kind") or "").strip().lower()
        try:
            if kind == "user":
                username = (request.data.get("username") or "").strip()
                target = User.objects.filter(username__iexact=username).first()
                if not target:
                    return Response(
                        {"detail": "User not found.", "code": "target_not_found"},
                        status=404,
                    )
                grant_user_share(doc, target=target, actor=request.user)
            elif kind == "organization":
                target_slug = (request.data.get("organization_slug") or "").strip()
                target = Organization.objects.filter(slug=target_slug, is_active=True).first()
                if not target:
                    return Response(
                        {"detail": "Organization not found.", "code": "target_not_found"},
                        status=404,
                    )
                grant_org_share(doc, target=target, actor=request.user)
            elif kind == "list":
                list_id = request.data.get("share_list_id")
                share_list = DocumentShareList.objects.filter(
                    pk=list_id, organization=org
                ).first()
                if not share_list:
                    return Response(
                        {"detail": "List not found.", "code": "target_not_found"},
                        status=404,
                    )
                grant_list_share(doc, share_list=share_list, actor=request.user)
            else:
                return Response(
                    {"detail": "kind must be user, organization, or list."},
                    status=400,
                )
        except DocumentError as exc:
            return _error(exc)
        doc.refresh_from_db()
        return Response(
            serialize_document(doc, request, include_shares=True),
            status=status.HTTP_201_CREATED,
        )


class OrganizationDocumentShareRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk, share_id):
        org, err = _member_org(request, slug)
        if err:
            return err
        doc = get_object_or_404(OrgDocument, pk=pk, organization=org)
        share = get_object_or_404(OrgDocumentShare, pk=share_id, document=doc)
        try:
            revoke_share(share, request.user)
        except DocumentError as exc:
            return _error(exc)
        return Response(serialize_document(doc, request, include_shares=True))


class OrganizationDocumentShareListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        org, err = _member_org(request, slug)
        if err:
            return err
        lists = DocumentShareList.objects.filter(organization=org).prefetch_related(
            "members__user__profile", "members__shared_organization"
        )
        return Response({"lists": [serialize_share_list(lst) for lst in lists]})

    def post(self, request, slug):
        org, err = _member_org(request, slug)
        if err:
            return err
        try:
            lst = create_share_list(
                organization=org, user=request.user, name=request.data.get("name") or ""
            )
        except DocumentError as exc:
            return _error(exc)
        return Response(serialize_share_list(lst), status=status.HTTP_201_CREATED)


class OrganizationDocumentShareListMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, list_id):
        org, err = _member_org(request, slug)
        if err:
            return err
        share_list = get_object_or_404(DocumentShareList, pk=list_id, organization=org)
        kind = (request.data.get("kind") or "").strip().lower()
        try:
            if kind == "user":
                username = (request.data.get("username") or "").strip()
                target = User.objects.filter(username__iexact=username).first()
                if not target:
                    return Response({"detail": "User not found."}, status=404)
                add_list_member(share_list, actor=request.user, user=target)
            elif kind == "organization":
                target_slug = (request.data.get("organization_slug") or "").strip()
                target = Organization.objects.filter(slug=target_slug, is_active=True).first()
                if not target:
                    return Response({"detail": "Organization not found."}, status=404)
                add_list_member(share_list, actor=request.user, organization=target)
            else:
                return Response({"detail": "kind must be user or organization."}, status=400)
        except DocumentError as exc:
            return _error(exc)
        share_list = DocumentShareList.objects.prefetch_related(
            "members__user__profile", "members__shared_organization"
        ).get(pk=share_list.pk)
        return Response(serialize_share_list(share_list), status=201)

    def delete(self, request, slug, list_id, member_id):
        org, err = _member_org(request, slug)
        if err:
            return err
        share_list = get_object_or_404(DocumentShareList, pk=list_id, organization=org)
        member = get_object_or_404(
            DocumentShareListMember, pk=member_id, share_list=share_list
        )
        try:
            remove_list_member(member, request.user)
        except DocumentError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
