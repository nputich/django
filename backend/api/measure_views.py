"""Measure Reading plugin: load a source, then review member revisions."""

from __future__ import annotations

import difflib
import re

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.bill_analysis import summarize_text
from api.board_service import is_org_admin, is_org_member
from api.models import Measure, MeasureMember, MeasureRevision, Organization, OrganizationMembership, PluginInstall
from api.nc_bills import bill_history, bill_text

PLUGIN_KEY = "measure_reading"
MEMBER_SLOTS = 8


def approved_install(org: Organization) -> PluginInstall | None:
    return (
        PluginInstall.objects.filter(
            organization=org,
            plugin__key=PLUGIN_KEY,
            status=PluginInstall.Status.APPROVED,
        )
        .select_related("plugin")
        .first()
    )


def _require_install(org, user):
    if not is_org_member(org, user):
        return None, Response({"detail": "Not a member of this organization."}, status=403)
    install = approved_install(org)
    if install is None:
        return None, Response({"detail": "Install the Measure Reading plugin first."}, status=403)
    return install, None


def _comparable(text: str) -> str:
    return re.sub(r"[ \t\r\n]+", "", text or "")


def _diff(base: str, proposed: str) -> str:
    if _comparable(base) == _comparable(proposed):
        return ""
    return "".join(
        difflib.unified_diff(
            (base or "").splitlines(keepends=True),
            (proposed or "").splitlines(keepends=True),
            fromfile="measure",
            tofile="revision",
        )
    )


def line_changes(measure: Measure) -> list[dict]:
    base = (measure.body or "").splitlines()
    changes = []
    for seat in measure.members.select_related("user"):
        revision = measure.revisions.filter(member=seat).first()
        if revision is None:
            continue
        proposed = (revision.body or "").splitlines()
        for index, original in enumerate(base):
            edited = proposed[index] if index < len(proposed) else ""
            if _comparable(edited) == _comparable(original):
                continue
                changes.append(
                    {
                        "id": f"{seat.id}:{index}",
                        "member_id": seat.id,
                        "label": seat.display_name(),
                        "color_index": seat.color_index,
                        "line_index": index,
                        "original": original,
                        "edited": edited,
                    }
                )
    return changes


def _payload(measure: Measure, selected_member_id=None) -> dict:
    revisions = {rev.member_id: rev for rev in measure.revisions.all()}
    members = []
    for seat in measure.members.select_related("user"):
        revision = revisions.get(seat.id)
        members.append(
            {
                "id": seat.id,
                "user_id": seat.user_id,
                "label": seat.display_name(),
                "color_index": seat.color_index,
                "has_revision": revision is not None,
            }
        )
    selected = None
    diff = ""
    if selected_member_id:
        seat = measure.members.filter(pk=selected_member_id).first()
        revision = revisions.get(seat.id) if seat else None
        if revision:
            selected = {"member_id": seat.id, "label": seat.display_name(), "body": revision.body}
            diff = _diff(measure.body, revision.body)
    return {
        "id": measure.id,
        "title": measure.title,
        "body": measure.body,
        "summary": measure.summary,
        "source_key": measure.source_key,
        "external_key": measure.external_key,
        "source_url": measure.source_url,
        "status": measure.status,
        "voting_open": measure.status == Measure.Status.VOTING,
        "passage_percent": measure.passage_percent,
        "members": members,
        "selected_revision": selected,
        "diff": diff,
        "changes": line_changes(measure),
        "colleagues": [
            {"user_id": membership.user_id, "username": membership.user.username, "label": membership.user.username}
            for membership in measure.organization.memberships.select_related("user")
        ],
    }


class MeasureListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        org = get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)
        install, error = _require_install(org, request.user)
        if error:
            return error
        rows = Measure.objects.filter(install=install)
        return Response([_payload(row) for row in rows])

    def post(self, request, slug):
        org = get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)
        if not is_org_admin(org, request.user):
            return Response({"detail": "Only an organization admin can load a measure."}, status=403)
        install, error = _require_install(org, request.user)
        if error:
            return error
        session_year = int(request.data.get("session_year") or 2025)
        chamber = (request.data.get("chamber") or "H").strip().upper()
        number = int(request.data.get("bill_number"))
        if chamber not in {"H", "S"}:
            return Response({"detail": "Chamber must be H or S."}, status=400)
        meta = bill_history(session_year, chamber, number)
        text = bill_text(session_year, chamber, number)
        citation = f"{chamber}{number}"
        measure = Measure.objects.create(
            install=install,
            organization=org,
            source_key="ncga",
            external_key=f"{session_year}:{chamber}:{number}",
            session_year=session_year,
            bill_type=chamber.lower(),
            bill_number=number,
            title=meta["title"],
            body=text,
            summary=summarize_text(meta["title"], citation, text),
            source_url=meta["source_url"],
            created_by=request.user,
            passage_percent=int(request.data.get("passage_percent") or 50),
        )
        return Response(_payload(measure), status=201)


class MeasureDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _measure(self, slug, pk, user):
        org = get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)
        install, error = _require_install(org, user)
        if error:
            return None, None, error
        measure = get_object_or_404(Measure, pk=pk, install=install)
        return org, measure, None

    def get(self, request, slug, pk):
        _org, measure, error = self._measure(slug, pk, request.user)
        if error:
            return error
        selected = request.query_params.get("member")
        return Response(_payload(measure, selected))

    def patch(self, request, slug, pk):
        org, measure, error = self._measure(slug, pk, request.user)
        if error:
            return error
        if not is_org_admin(org, request.user):
            return Response({"detail": "Only an organization admin can edit the measure."}, status=403)
        if measure.status == Measure.Status.VOTING:
            return Response({"detail": "Voting has started. The measure text is locked."}, status=400)
        if "title" in request.data:
            measure.title = (request.data.get("title") or "")[:300]
        if "body" in request.data:
            measure.body = request.data.get("body") or ""
        if "passage_percent" in request.data:
            measure.passage_percent = max(1, min(100, int(request.data.get("passage_percent") or 50)))
        if "summary" in request.data:
            measure.summary = request.data.get("summary") or ""
        measure.save()
        return Response(_payload(measure))

    def delete(self, request, slug, pk):
        org, measure, error = self._measure(slug, pk, request.user)
        if error:
            return error
        if not is_org_admin(org, request.user):
            return Response({"detail": "Only an organization admin can delete a measure."}, status=403)
        if measure.status == Measure.Status.VOTING:
            return Response({"detail": "Voting has started. This copy cannot be deleted."}, status=400)
        measure.delete()
        return Response(status=204)


class MeasureVotingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        org = get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)
        if not is_org_admin(org, request.user):
            return Response({"detail": "Only an organization admin can start voting."}, status=403)
        install, error = _require_install(org, request.user)
        if error:
            return error
        measure = get_object_or_404(Measure, pk=pk, install=install)
        measure.status = Measure.Status.VOTING
        measure.save(update_fields=["status", "updated_at"])
        return Response(_payload(measure))


class MeasureMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        org = get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)
        if not is_org_admin(org, request.user):
            return Response({"detail": "Only an organization admin can invite members."}, status=403)
        install, error = _require_install(org, request.user)
        if error:
            return error
        measure = get_object_or_404(Measure, pk=pk, install=install)
        user = get_object_or_404(User, pk=request.data.get("user_id"))
        if not OrganizationMembership.objects.filter(organization=org, user=user).exists():
            return Response({"detail": "That person is not in this organization."}, status=400)
        taken = set(measure.members.values_list("color_index", flat=True))
        color = next((index for index in range(MEMBER_SLOTS) if index not in taken), len(taken) % MEMBER_SLOTS)
        label = (request.data.get("label") or "")[:80]
        seat = measure.members.filter(user=user).first()
        if seat is None:
            MeasureMember.objects.create(
                measure=measure, user=user, label=label, color_index=color
            )
        else:
            seat.label = label
            seat.save(update_fields=["label"])
        return Response(_payload(measure), status=201)


class MeasureRevisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        org = get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)
        install, error = _require_install(org, request.user)
        if error:
            return error
        measure = get_object_or_404(Measure, pk=pk, install=install)
        seat = measure.members.filter(user=request.user).first()
        if seat is None:
            if not is_org_member(org, request.user):
                return Response({"detail": "You are not a member of this organization."}, status=403)
            taken = set(measure.members.values_list("color_index", flat=True))
            color = next((index for index in range(MEMBER_SLOTS) if index not in taken), 0)
            seat = MeasureMember.objects.create(
                measure=measure,
                user=request.user,
                label=request.user.username,
                color_index=color,
            )
        body = request.data.get("body") or ""
        MeasureRevision.objects.update_or_create(
            measure=measure, member=seat, defaults={"body": body}
        )
        return Response(_payload(measure, seat.id))


class MeasureReviewRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, pk):
        from django.core.exceptions import ValidationError

        from api.inbox_service import get_personal_mailbox, send_new_message

        org = get_object_or_404(Organization, slug=slug, status=Organization.Status.ACTIVE)
        install, error = _require_install(org, request.user)
        if error:
            return error
        measure = get_object_or_404(Measure, pk=pk, install=install)
        user_ids = request.data.get("user_ids") or []
        note = (request.data.get("message") or "").strip()
        if not user_ids:
            return Response({"detail": "Choose at least one person."}, status=400)
        mailbox = get_personal_mailbox(request.user)
        subject = f"Review requested: {measure.title or 'a measure'}"
        body = note or f"{request.user.username} asked you to review their changes on {measure.title}."
        sent = []
        for user_id in user_ids:
            membership = org.memberships.filter(user_id=user_id).select_related("user").first()
            if membership is None or membership.user_id == request.user.id:
                continue
            try:
                send_new_message(
                    mailbox=mailbox,
                    subject=subject,
                    body=body,
                    to_username=membership.user.username,
                )
            except ValidationError as exc:
                return Response({"detail": str(exc)}, status=400)
            sent.append(membership.user.username)
        return Response({"sent": sent})
