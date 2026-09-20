"""Question tag catalog + tagging endpoints for org admins."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MeetingSlide, Organization, QuestionTag, SurveyQuestion
from .org_access import get_admin_organization
from .question_tags import (
    TagError,
    catalog_payload,
    count_other_uses,
    create_custom_tag,
    serialize_tag,
    set_tags,
    tags_for_slide,
    tags_for_survey_question,
    update_custom_tag,
)


def _admin_org(request, slug):
    try:
        return get_admin_organization(request.user, slug), None
    except Organization.DoesNotExist:
        return None, Response(
            {"detail": "Organization not found or you are not an admin."},
            status=status.HTTP_404_NOT_FOUND,
        )


def _error(exc: TagError):
    return Response({"detail": exc.message, "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)


class QuestionTagCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        return Response(catalog_payload(organization, query=(request.query_params.get("q") or "").strip()))

    def post(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        try:
            tag = create_custom_tag(
                organization=organization,
                label=request.data.get("label") or "",
                category=request.data.get("category") or "",
                user=request.user,
            )
        except TagError as exc:
            return _error(exc)
        return Response(serialize_tag(tag), status=status.HTTP_201_CREATED)


class QuestionTagDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug, pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        tag = get_object_or_404(QuestionTag, pk=pk)
        try:
            tag = update_custom_tag(
                tag,
                organization=organization,
                label=request.data.get("label"),
                description=request.data.get("description"),
                is_active=request.data.get("is_active"),
                category=request.data.get("category"),
            )
        except TagError as exc:
            return _error(exc)
        return Response(serialize_tag(tag))


def _tag_response(tags, organization, question_key, **exclude):
    return {
        "tags": [serialize_tag(t) for t in tags],
        "question_key": question_key,
        "other_uses": count_other_uses(organization, question_key, **exclude),
    }


class MeetingSlideTagsView(APIView):
    """GET current tags + reuse counts; PUT {tag_ids, scope} to replace."""

    permission_classes = [IsAuthenticated]

    def _slide(self, organization, meeting_pk, slide_pk):
        return get_object_or_404(
            MeetingSlide.objects.select_related("meeting__organization"),
            pk=slide_pk,
            meeting_id=meeting_pk,
            meeting__organization=organization,
        )

    def get(self, request, slug, pk, slide_pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        slide = self._slide(organization, pk, slide_pk)
        return Response(
            _tag_response(tags_for_slide(slide), organization, slide.question_key, exclude_slide_id=slide.id)
        )

    def put(self, request, slug, pk, slide_pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        slide = self._slide(organization, pk, slide_pk)
        try:
            set_tags(
                organization=organization,
                question_key=slide.question_key,
                tag_ids=request.data.get("tag_ids") or [],
                scope=request.data.get("scope") or "all",
                slide=slide,
                user=request.user,
            )
        except TagError as exc:
            return _error(exc)
        return Response(
            _tag_response(tags_for_slide(slide), organization, slide.question_key, exclude_slide_id=slide.id)
        )


class SurveyQuestionTagsView(APIView):
    permission_classes = [IsAuthenticated]

    def _question(self, organization, survey_pk, question_pk):
        return get_object_or_404(
            SurveyQuestion.objects.select_related("survey__organization"),
            pk=question_pk,
            survey_id=survey_pk,
            survey__organization=organization,
        )

    def get(self, request, slug, pk, question_pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        q = self._question(organization, pk, question_pk)
        return Response(
            _tag_response(tags_for_survey_question(q), organization, q.question_key, exclude_question_id=q.id)
        )

    def put(self, request, slug, pk, question_pk):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        q = self._question(organization, pk, question_pk)
        try:
            set_tags(
                organization=organization,
                question_key=q.question_key,
                tag_ids=request.data.get("tag_ids") or [],
                scope=request.data.get("scope") or "all",
                survey_question=q,
                user=request.user,
            )
        except TagError as exc:
            return _error(exc)
        return Response(
            _tag_response(tags_for_survey_question(q), organization, q.question_key, exclude_question_id=q.id)
        )


class QuestionUsesPreviewView(APIView):
    """GET ?text=… → how many past uses match this question text (for editors)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization, err = _admin_org(request, slug)
        if err:
            return err
        from .question_identity import question_key_for  # noqa: PLC0415
        from .question_tags import tags_for_keys  # noqa: PLC0415

        key = question_key_for(request.query_params.get("text") or "")
        tags = tags_for_keys(organization, {key}).get(key, []) if key else []
        return Response(
            {
                "question_key": key,
                "other_uses": count_other_uses(organization, key),
                "tags": [serialize_tag(t) for t in tags],
            }
        )
