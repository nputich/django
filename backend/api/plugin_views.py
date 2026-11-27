"""Plugin warehouse and NC Voter Record PowerQuery."""

from __future__ import annotations

import csv
import io
import threading
import zipfile
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from api.board_service import is_org_admin, is_org_member
from api.models import Organization, PluginDefinition, PluginInstall, VoterFile, VoterRecord
from api.voter_nc import (
    QUERY_FIELDS,
    compare_files,
    match_list,
    parse_comparison_list,
    parse_voter_file,
)

NC_KEY = "nc_voter_powerquery"


def _store_upload(upload, prefix: str) -> str:
    root = Path(settings.BASE_DIR) / "private_voter_files" / prefix
    root.mkdir(parents=True, exist_ok=True)
    safe_name = Path(upload.name).name
    path = root / safe_name
    if path.exists():
        path = root / f"{path.stem}_{prefix}{path.suffix}"
    with path.open("wb") as handle:
        for chunk in upload.chunks():
            handle.write(chunk)
    return str(path)


def _queue_parse(parser, file_id: int) -> None:
    if getattr(settings, "VOTER_PARSE_INLINE", False):
        parser(file_id)
        return
    transaction.on_commit(lambda: _schedule(parser, file_id))


def _schedule(parser, file_id: int) -> None:
    if getattr(settings, "VOTER_PARSE_INLINE", False):
        parser(file_id)
        return

    def run():
        close_old_connections()
        try:
            parser(file_id)
        finally:
            close_old_connections()

    threading.Thread(target=run, daemon=True).start()


APPROVER_SCOPES = (
    Organization.GeographicScope.NATIONAL,
    Organization.GeographicScope.STATE_PROVINCE,
)


def user_can_submit_official(user) -> bool:
    """Staff, or an owner/admin of a Communibetter organization, may submit the shared file."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return Organization.objects.filter(
        is_communibetter=True,
        status=Organization.Status.ACTIVE,
        memberships__user=user,
        memberships__role__in=("owner", "admin"),
    ).exists()


def user_can_review(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Organization.objects.filter(
        is_communibetter=True,
        geographic_scope__in=APPROVER_SCOPES,
        status=Organization.Status.ACTIVE,
        memberships__user=user,
        memberships__role__in=("owner", "admin"),
    ).exists()


def can_review_plugin_access(user, organization) -> bool:
    """Communibetter state and national org admins review voter-plugin requests."""
    if not user or not user.is_authenticated:
        return False
    if organization is None:
        return user_can_review(user)
    return bool(
        organization.is_communibetter
        and organization.geographic_scope in APPROVER_SCOPES
        and is_org_admin(organization, user)
    )


def _install_status(definition: PluginDefinition, organization):
    if not definition.requires_approval:
        return PluginInstall.Status.APPROVED
    if (
        organization is not None
        and organization.is_communibetter
        and organization.geographic_scope in APPROVER_SCOPES
    ):
        return PluginInstall.Status.APPROVED
    return PluginInstall.Status.PENDING


def _definition_payload(definition: PluginDefinition, install: PluginInstall | None):
    return {
        "key": definition.key,
        "name": definition.name,
        "description": definition.description,
        "audience": definition.audience,
        "requires_approval": definition.requires_approval,
        "installed": install is not None,
        "status": None if install is None else install.status,
        "request_comment": "" if install is None else install.request_comment,
        "decision_comment": "" if install is None else install.decision_comment,
    }


def _request_payload(install: PluginInstall):
    if install.user_id:
        owner_kind = "personal"
        owner_label = install.user.username
    else:
        owner_kind = "organization"
        owner_label = install.organization.name
    return {
        "id": install.id,
        "plugin_key": install.plugin.key,
        "plugin_name": install.plugin.name,
        "owner_kind": owner_kind,
        "owner_label": owner_label,
        "status": install.status,
        "request_comment": install.request_comment,
        "decision_comment": install.decision_comment,
        "requested_by": None if install.installed_by_id is None else install.installed_by.username,
        "installed_at": install.installed_at,
        "decided_at": install.decided_at,
    }


def _upload_label(request) -> str:
    return (request.data.get("label") or "").strip()[:120]


def _file_payload(voter_file: VoterFile):
    return {
        "id": voter_file.id,
        "source": voter_file.source,
        "original_filename": voter_file.original_filename,
        "label": voter_file.label,
        "row_count": voter_file.row_count,
        "rows_skipped": voter_file.rows_skipped,
        "skip_samples": voter_file.skip_samples or [],
        "status": voter_file.status,
        "upload_received": True,
        "error": voter_file.error,
        "parsed_at": voter_file.parsed_at,
        "is_current_official": voter_file.is_current_official,
        "created_at": voter_file.created_at,
    }


class PluginOwnerMixin:
    def owner_kind(self):
        return "personal" if self.kwargs.get("slug") is None else "organization"

    def organization(self):
        slug = self.kwargs.get("slug")
        if not slug:
            return None
        return get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)

    def can_manage(self, request):
        org = self.organization()
        if org is None:
            return True
        return is_org_admin(org, request.user)

    def can_read(self, request):
        org = self.organization()
        if org is None:
            return True
        return is_org_member(org, request.user)

    def install_for(self, plugin: PluginDefinition):
        org = self.organization()
        if org is None:
            return PluginInstall.objects.filter(plugin=plugin, user=self.request.user).first()
        return PluginInstall.objects.filter(plugin=plugin, organization=org).first()

    def visible_files(self, install: PluginInstall | None):
        official = VoterFile.objects.filter(
            source=VoterFile.Source.OFFICIAL, is_current_official=True
        )
        if install is None:
            return official
        return VoterFile.objects.filter(install=install) | official


class PluginCatalogView(PluginOwnerMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug=None):
        if not self.can_read(request):
            return Response({"detail": "Not a member of this organization."}, status=403)
        kind = self.owner_kind()
        org = self.organization()
        installs = PluginInstall.objects.filter(user=request.user) if org is None else PluginInstall.objects.filter(organization=org)
        by_plugin = {install.plugin_id: install for install in installs}
        rows = []
        for definition in PluginDefinition.objects.filter(enabled=True).order_by("name"):
            if definition.allows(kind):
                rows.append(_definition_payload(definition, by_plugin.get(definition.id)))
        return Response({
            "plugins": rows,
            "can_manage": self.can_manage(request),
            "can_review": can_review_plugin_access(request.user, org),
        })

    def post(self, request, slug=None):
        if not self.can_manage(request):
            return Response({"detail": "Only an organization admin can add a plugin."}, status=403)
        key = (request.data.get("key") or "").strip()
        definition = get_object_or_404(PluginDefinition, key=key, enabled=True)
        if not definition.allows(self.owner_kind()):
            return Response({"detail": "This plugin cannot be added here."}, status=400)
        org = self.organization()
        lookup = {"plugin": definition, "user": request.user} if org is None else {"plugin": definition, "organization": org}
        comment = (request.data.get("comment") or "").strip()
        install = PluginInstall.objects.filter(**lookup).first()
        created = install is None
        access_status = _install_status(definition, org)
        if created:
            install = PluginInstall.objects.create(
                plugin=definition,
                user=request.user if org is None else None,
                organization=org,
                installed_by=request.user,
                status=access_status,
                request_comment=comment,
            )
        elif install.status != PluginInstall.Status.APPROVED:
            install.status = access_status
            install.request_comment = comment
            install.decision_comment = ""
            install.decided_by = None
            install.decided_at = None
            install.installed_by = request.user
            install.save()
        payload = _definition_payload(definition, install)
        if install.status == PluginInstall.Status.PENDING:
            payload["message"] = (
                "Request sent. A Communibetter state or national admin will review it."
            )
        elif install.status == PluginInstall.Status.APPROVED and created:
            payload["message"] = "Plugin added."
        return Response(
            payload,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PluginInstallDetailView(PluginOwnerMixin, APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, key, slug=None):
        if not self.can_manage(request):
            return Response({"detail": "Only an organization admin can remove a plugin."}, status=403)
        definition = get_object_or_404(PluginDefinition, key=key)
        org = self.organization()
        lookup = {"plugin": definition, "user": request.user} if org is None else {"plugin": definition, "organization": org}
        PluginInstall.objects.filter(**lookup).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PluginAccessRequestListView(PluginOwnerMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug=None):
        org = self.organization()
        if not can_review_plugin_access(request.user, org):
            return Response({"detail": "You cannot review plugin access."}, status=403)
        installs = (
            PluginInstall.objects.filter(plugin__requires_approval=True)
            .select_related("plugin", "user", "organization", "installed_by")
            .order_by("status", "-installed_at")
        )
        return Response({"requests": [_request_payload(item) for item in installs[:200]]})


class PluginAccessDecisionView(PluginOwnerMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, slug=None):
        org = self.organization()
        if not can_review_plugin_access(request.user, org):
            return Response({"detail": "You cannot review plugin access."}, status=403)
        install = get_object_or_404(
            PluginInstall.objects.select_related("plugin", "user", "organization", "installed_by"),
            pk=pk,
            plugin__requires_approval=True,
        )
        decision = (request.data.get("decision") or "").strip()
        if decision not in ("approve", "deny"):
            return Response({"detail": "Choose approve or deny."}, status=400)
        install.status = (
            PluginInstall.Status.APPROVED if decision == "approve" else PluginInstall.Status.DENIED
        )
        install.decision_comment = (request.data.get("comment") or "").strip()
        install.decided_by = request.user
        install.decided_at = timezone.now()
        install.save(update_fields=["status", "decision_comment", "decided_by", "decided_at"])
        return Response(_request_payload(install))


class VoterPluginBase(PluginOwnerMixin, APIView):
    permission_classes = [IsAuthenticated]

    def plugin(self):
        return get_object_or_404(PluginDefinition, key=NC_KEY, enabled=True)

    def require_install(self, request):
        if not self.can_read(request):
            return None, Response({"detail": "Not a member of this organization."}, status=403)
        install = self.install_for(self.plugin())
        org = self.organization()
        reviewer = can_review_plugin_access(request.user, org) or (
            org is None and user_can_review(request.user)
        )
        if install is None and reviewer:
            install = PluginInstall.objects.create(
                plugin=self.plugin(),
                user=request.user if org is None else None,
                organization=org,
                installed_by=request.user,
                status=PluginInstall.Status.APPROVED,
            )
        if install is None:
            return None, Response({"detail": "Add NC Voter Record PowerQuery first."}, status=404)
        if install.status != PluginInstall.Status.APPROVED:
            detail = "This plugin is waiting for approval."
            if install.status == PluginInstall.Status.DENIED:
                detail = "This plugin request was denied."
            return None, Response(
                {"detail": detail, "status": install.status, "decision_comment": install.decision_comment},
                status=403,
            )
        return install, None

    def owned_file(self, request, file_id, install):
        voter_file = get_object_or_404(VoterFile, pk=file_id)
        if voter_file.is_current_official:
            return voter_file
        if voter_file.install_id != install.id:
            return None
        return voter_file


class VoterFileListView(VoterPluginBase):
    def get(self, request, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        files = self.visible_files(install).order_by("-created_at")
        return Response(
            {
                "files": [_file_payload(item) for item in files[:100]],
                "can_submit_official": user_can_submit_official(request.user),
                "can_manage": self.can_manage(request),
            }
        )

    def post(self, request, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        if not self.can_read(request):
            return Response({"detail": "You cannot upload files for this owner."}, status=403)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Choose a file to upload."}, status=400)
        source = request.data.get("source") or VoterFile.Source.OWNER_UPLOAD
        if source not in (VoterFile.Source.OWNER_UPLOAD, VoterFile.Source.COMPARISON_LIST):
            return Response({"detail": "Unsupported upload type."}, status=400)
        stored = _store_upload(upload, f"install-{install.id}")
        voter_file = VoterFile.objects.create(
            install=install,
            source=source,
            original_filename=Path(upload.name).name,
            label=_upload_label(request),
            stored_path=stored,
            submitted_by=request.user,
            status=VoterFile.Status.QUEUED,
        )
        parser = parse_comparison_list if source == VoterFile.Source.COMPARISON_LIST else parse_voter_file
        _queue_parse(parser, voter_file.id)
        voter_file.refresh_from_db()
        return Response(_file_payload(voter_file), status=status.HTTP_201_CREATED)


class OfficialVoterFileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_can_submit_official(request.user):
            return Response(
                {"detail": "Only a Communibetter admin can submit the official file."},
                status=403,
            )
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Choose a file to upload."}, status=400)
        stored = _store_upload(upload, "official")
        with transaction.atomic():
            VoterFile.objects.filter(is_current_official=True).update(is_current_official=False)
            voter_file = VoterFile.objects.create(
                install=None,
                source=VoterFile.Source.OFFICIAL,
                original_filename=Path(upload.name).name,
                label=_upload_label(request),
                stored_path=stored,
                submitted_by=request.user,
                is_current_official=True,
                status=VoterFile.Status.QUEUED,
            )
        _queue_parse(parse_voter_file, voter_file.id)
        voter_file.refresh_from_db()
        return Response(_file_payload(voter_file), status=status.HTTP_201_CREATED)


class VoterCompareView(VoterPluginBase):
    def post(self, request, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        file_a = self.owned_file(request, request.data.get("file_a"), install)
        file_b = self.owned_file(request, request.data.get("file_b"), install)
        if file_a is None or file_b is None:
            return Response({"detail": "Choose two files you can access."}, status=400)
        if file_a.status != VoterFile.Status.READY or file_b.status != VoterFile.Status.READY:
            return Response({"detail": "Both files must finish parsing first."}, status=400)
        county = (request.data.get("county") or "").strip()
        result = compare_files(file_a, file_b, county=county)
        result.pop("only_in_a_rows", None)
        result.pop("only_in_b_rows", None)
        return Response(result)


class VoterQueryView(VoterPluginBase):
    def post(self, request, file_id, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        voter_file = self.owned_file(request, file_id, install)
        if voter_file is None:
            return Response({"detail": "That file is not available."}, status=404)
        if voter_file.status != VoterFile.Status.READY:
            return Response({"detail": "This file is not ready to query."}, status=400)
        qs = _apply_filters(voter_file.records.all(), request.data.get("filters") or [])
        name = (request.data.get("name") or "").strip()
        if name:
            qs = qs.filter(Q(last_name__istartswith=name) | Q(first_name__istartswith=name))
        county = (request.data.get("county") or "").strip()
        if county:
            qs = qs.filter(county__iexact=county)
        status_value = (request.data.get("status") or "").strip()
        if status_value:
            qs = qs.filter(status__iexact=status_value)
        party = (request.data.get("party") or "").strip()
        if party:
            qs = qs.filter(party__iexact=party)
        try:
            limit = min(int(request.data.get("limit") or 100), 500)
        except (TypeError, ValueError):
            limit = 100
        fields = request.data.get("fields") or list(QUERY_FIELDS)
        fields = [field for field in fields if field in QUERY_FIELDS]
        if not fields:
            fields = list(QUERY_FIELDS)
        rows = list(qs.order_by("last_name", "first_name").values(*fields)[:limit])
        return Response({"count": qs.count(), "fields": fields, "rows": rows})


class VoterExportView(VoterPluginBase):
    def post(self, request, file_id, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        voter_file = self.owned_file(request, file_id, install)
        if voter_file is None:
            return Response({"detail": "That file is not available."}, status=404)
        qs = _apply_filters(voter_file.records.all(), request.data.get("filters") or [])
        county = (request.data.get("county") or "").strip()
        if county:
            qs = qs.filter(county__iexact=county)
        name = (request.data.get("name") or "").strip()
        if name:
            qs = qs.filter(Q(last_name__istartswith=name) | Q(first_name__istartswith=name))
        party = (request.data.get("party") or "").strip()
        if party:
            qs = qs.filter(party__iexact=party)
        try:
            limit = min(int(request.data.get("limit") or 5000), 20000)
        except (TypeError, ValueError):
            limit = 5000
        fields = [field for field in (request.data.get("fields") or QUERY_FIELDS) if field in QUERY_FIELDS]
        if not fields:
            fields = list(QUERY_FIELDS)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for row in qs.order_by("county", "last_name").values(*fields)[:limit]:
            writer.writerow(row)
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="voter-query.csv"'
        return response


class VoterMatchListView(VoterPluginBase):
    def post(self, request, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        voter_file = self.owned_file(request, request.data.get("file_id"), install)
        comparison = self.owned_file(request, request.data.get("list_id"), install)
        if voter_file is None or comparison is None:
            return Response({"detail": "Choose a voter file and a comparison list."}, status=400)
        if comparison.source != VoterFile.Source.COMPARISON_LIST:
            return Response({"detail": "The second file must be a comparison list."}, status=400)
        return Response(match_list(voter_file, comparison))


class VoterCountyPacketView(VoterPluginBase):
    def post(self, request, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        file_a = self.owned_file(request, request.data.get("file_a"), install)
        file_b = self.owned_file(request, request.data.get("file_b"), install)
        if file_a is None or file_b is None:
            return Response({"detail": "Choose two files you can access."}, status=400)
        side = request.data.get("missing_side") or "only_in_a"
        county = (request.data.get("county") or "").strip()
        result = compare_files(file_a, file_b, county=county, sample_limit=0)
        rows = result["only_in_a_rows"] if side == "only_in_a" else result["only_in_b_rows"]
        grouped = {}
        for record in rows:
            grouped.setdefault(record.county or "UNKNOWN", []).append(record)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for county_name, records in sorted(grouped.items()):
                buffer = io.StringIO()
                writer = csv.DictWriter(
                    buffer,
                    fieldnames=["county", "ncid", "last_name", "first_name", "address", "reason"],
                )
                writer.writeheader()
                for record in records:
                    writer.writerow(
                        {
                            "county": record.county,
                            "ncid": record.ncid,
                            "last_name": record.last_name,
                            "first_name": record.first_name,
                            "address": record.address,
                            "reason": "Missing from the other file",
                        }
                    )
                safe = "".join(ch if ch.isalnum() else "_" for ch in county_name) or "UNKNOWN"
                bundle.writestr(f"{safe}.csv", buffer.getvalue())
        response = HttpResponse(archive.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="county-voter-packets.zip"'
        return response


def _apply_filters(qs, filters):
    allowed_ops = {"eq": "", "contains": "__icontains"}
    for item in filters:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        op = item.get("op") or "eq"
        if field not in QUERY_FIELDS or op not in allowed_ops:
            continue
        value = item.get("value")
        if value in (None, ""):
            continue
        lookup = f"{field}__iexact" if op == "eq" else f"{field}{allowed_ops[op]}"
        qs = qs.filter(**{lookup: value})
    return qs


class VoterRecordBrowseView(VoterPluginBase):
    """GET browse used by the query screen for simple name and county search."""

    def get(self, request, file_id, slug=None):
        install, error = self.require_install(request)
        if error:
            return error
        voter_file = self.owned_file(request, file_id, install)
        if voter_file is None:
            return Response({"detail": "That file is not available."}, status=404)
        qs = VoterRecord.objects.filter(voter_file=voter_file)
        county = (request.query_params.get("county") or "").strip()
        if county:
            qs = qs.filter(county__iexact=county)
        status_value = (request.query_params.get("status") or "").strip()
        if status_value:
            qs = qs.filter(status__iexact=status_value)
        party = (request.query_params.get("party") or "").strip()
        if party:
            qs = qs.filter(party__iexact=party)
        name = (request.query_params.get("name") or "").strip()
        if name:
            qs = qs.filter(Q(last_name__istartswith=name) | Q(first_name__istartswith=name))
        if request.query_params.get("preview") == "1":
            rows = list(qs.order_by("id").values(*QUERY_FIELDS)[:8])
            return Response({"count": len(rows), "rows": rows})
        rows = list(qs.order_by("last_name", "first_name").values(*QUERY_FIELDS)[:100])
        return Response({"count": qs.count(), "rows": rows})
