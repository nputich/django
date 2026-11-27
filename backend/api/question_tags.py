"""
Question tags: shared catalog + per-org custom tags, linked to questions by
normalized text (``question_key``) so a tag follows a question across every
meeting and survey where it was asked — including past ones.
"""

from __future__ import annotations

from collections import defaultdict

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.utils.text import slugify

from .models import (
    MeetingSlide,
    Organization,
    QuestionTag,
    QuestionTagLink,
    SurveyQuestion,
)


class TagError(ValueError):
    def __init__(self, message: str, *, code: str = "tag_error"):
        super().__init__(message)
        self.message = message
        self.code = code


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #


def available_tags(organization: Organization):
    return QuestionTag.objects.filter(is_active=True).filter(
        Q(organization__isnull=True) | Q(organization=organization)
    )


def serialize_tag(tag: QuestionTag, *, usage: int | None = None) -> dict:
    data = {
        "id": tag.id,
        "slug": tag.slug,
        "label": tag.label,
        "category": tag.category,
        "category_label": tag.get_category_display(),
        "description": tag.description,
        "is_custom": tag.organization_id is not None,
    }
    if usage is not None:
        data["usage"] = usage
    return data


def catalog_payload(organization: Organization, *, query: str = "") -> dict:
    qs = available_tags(organization)
    if query:
        qs = qs.filter(Q(label__icontains=query) | Q(slug__icontains=query))
    usage = dict(
        QuestionTagLink.objects.filter(organization=organization)
        .values("tag_id")
        .annotate(n=Count("question_key", distinct=True))
        .values_list("tag_id", "n")
    )
    grouped: dict[str, list] = defaultdict(list)
    for tag in qs.order_by("category", "label"):
        grouped[tag.category].append(serialize_tag(tag, usage=usage.get(tag.id, 0)))
    return {
        "categories": [
            {"key": key, "label": label, "tags": grouped.get(key, [])}
            for key, label in QuestionTag.Category.choices
            if grouped.get(key)
        ],
        "tags": [t for tags in grouped.values() for t in tags],
    }


def create_custom_tag(
    *, organization: Organization, label: str, category: str = "", user: User | None = None
) -> QuestionTag:
    label = (label or "").strip()
    if len(label) < 2:
        raise TagError("Tag names need at least 2 characters.", code="label_too_short")
    slug = slugify(label)[:80]
    if not slug:
        raise TagError("Tag name must contain letters or numbers.", code="invalid_label")
    if category not in dict(QuestionTag.Category.choices):
        category = QuestionTag.Category.CUSTOM
    existing = available_tags(organization).filter(slug=slug).first()
    if existing:
        return existing
    return QuestionTag.objects.create(
        organization=organization,
        slug=slug,
        label=label,
        category=category,
        created_by=user,
    )


def update_custom_tag(tag: QuestionTag, *, organization: Organization, **fields) -> QuestionTag:
    if tag.organization_id != organization.id:
        raise TagError("Only custom tags created by your organization can be edited.", code="not_owner")
    changed = []
    if "label" in fields and fields["label"] is not None:
        label = fields["label"].strip()
        if len(label) < 2:
            raise TagError("Tag names need at least 2 characters.", code="label_too_short")
        tag.label = label
        changed.append("label")
    if "description" in fields and fields["description"] is not None:
        tag.description = fields["description"].strip()[:255]
        changed.append("description")
    if "is_active" in fields and fields["is_active"] is not None:
        tag.is_active = bool(fields["is_active"])
        changed.append("is_active")
    if "category" in fields and fields["category"] in dict(QuestionTag.Category.choices):
        tag.category = fields["category"]
        changed.append("category")
    if changed:
        tag.save(update_fields=changed)
    return tag


# --------------------------------------------------------------------------- #
# Links
# --------------------------------------------------------------------------- #


def _resolve_tags(organization: Organization, tag_ids) -> list[QuestionTag]:
    ids = {int(i) for i in (tag_ids or []) if str(i).strip()}
    if not ids:
        return []
    tags = list(available_tags(organization).filter(id__in=ids))
    if len(tags) != len(ids):
        raise TagError("One or more tags are not available to this organization.", code="unknown_tag")
    return tags


def tags_for_keys(organization: Organization, keys: set[str]) -> dict[str, list[QuestionTag]]:
    """Org-wide tags per question_key."""
    result: dict[str, list[QuestionTag]] = defaultdict(list)
    if not keys:
        return result
    links = (
        QuestionTagLink.objects.filter(
            organization=organization,
            question_key__in=keys,
            slide__isnull=True,
            survey_question__isnull=True,
        )
        .select_related("tag")
        .order_by("tag__category", "tag__label")
    )
    for link in links:
        result[link.question_key].append(link.tag)
    return result


def tags_for_slide(slide: MeetingSlide) -> list[QuestionTag]:
    org = slide.meeting.organization
    seen: dict[int, QuestionTag] = {}
    for tag in tags_for_keys(org, {slide.question_key}).get(slide.question_key, []):
        seen[tag.id] = tag
    for link in slide.tag_links.select_related("tag"):
        seen[link.tag_id] = link.tag
    return sorted(seen.values(), key=lambda t: (t.category, t.label))


def tags_for_survey_question(question: SurveyQuestion) -> list[QuestionTag]:
    org = question.survey.organization
    seen: dict[int, QuestionTag] = {}
    for tag in tags_for_keys(org, {question.question_key}).get(question.question_key, []):
        seen[tag.id] = tag
    for link in question.tag_links.select_related("tag"):
        seen[link.tag_id] = link.tag
    return sorted(seen.values(), key=lambda t: (t.category, t.label))


def count_other_uses(organization: Organization, question_key: str, *, exclude_slide_id=None, exclude_question_id=None) -> dict:
    """How many other places this exact question has been asked (for the 'apply to past?' prompt)."""
    if not question_key:
        return {"meetings": 0, "surveys": 0, "responses": 0}
    slides = MeetingSlide.objects.filter(
        meeting__organization=organization, question_key=question_key
    )
    if exclude_slide_id:
        slides = slides.exclude(pk=exclude_slide_id)
    questions = SurveyQuestion.objects.filter(
        survey__organization=organization, question_key=question_key
    )
    if exclude_question_id:
        questions = questions.exclude(pk=exclude_question_id)
    from .models import MeetingResponse, SurveyAnswer  # noqa: PLC0415

    responses = MeetingResponse.objects.filter(slide__in=slides).count() + SurveyAnswer.objects.filter(
        question__in=questions
    ).count()
    return {
        "meetings": slides.values("meeting_id").distinct().count(),
        "surveys": questions.values("survey_id").distinct().count(),
        "responses": responses,
    }


@transaction.atomic
def set_tags(
    *,
    organization: Organization,
    question_key: str,
    tag_ids,
    scope: str = "all",
    slide: MeetingSlide | None = None,
    survey_question: SurveyQuestion | None = None,
    user: User | None = None,
) -> list[QuestionTag]:
    """
    Replace the tag set for a question.

    scope="all"  → org-wide by question_key (past + future uses).
    scope="this" → only this slide / survey question.
    """
    tags = _resolve_tags(organization, tag_ids)
    if scope not in ("all", "this"):
        raise TagError("scope must be 'all' or 'this'.", code="invalid_scope")

    if scope == "all":
        if not question_key:
            raise TagError("This question has no text to match on.", code="no_question_key")
        QuestionTagLink.objects.filter(
            organization=organization,
            question_key=question_key,
            slide__isnull=True,
            survey_question__isnull=True,
        ).delete()
        # Per-use links for the same key are now redundant for these tags.
        QuestionTagLink.objects.filter(
            organization=organization, question_key=question_key, tag__in=tags
        ).delete()
        QuestionTagLink.objects.bulk_create(
            [
                QuestionTagLink(
                    organization=organization,
                    tag=tag,
                    question_key=question_key,
                    created_by=user,
                )
                for tag in tags
            ]
        )
        return tags

    if slide is None and survey_question is None:
        raise TagError("scope='this' needs a slide or survey question.", code="target_required")
    target = {"slide": slide} if slide is not None else {"survey_question": survey_question}
    QuestionTagLink.objects.filter(organization=organization, **target).delete()
    org_wide = {t.id for t in tags_for_keys(organization, {question_key}).get(question_key, [])}
    QuestionTagLink.objects.bulk_create(
        [
            QuestionTagLink(
                organization=organization,
                tag=tag,
                question_key=question_key or "",
                created_by=user,
                **target,
            )
            for tag in tags
            if tag.id not in org_wide
        ]
    )
    return tags


def apply_payload_tags(
    *, organization: Organization, slide: MeetingSlide | None = None, survey_question: SurveyQuestion | None = None, payload: dict, user=None
) -> None:
    """Apply ``tag_ids`` / ``tag_scope`` carried on a slide or question payload."""
    if "tag_ids" not in payload:
        return
    target = slide if slide is not None else survey_question
    set_tags(
        organization=organization,
        question_key=target.question_key,
        tag_ids=payload.get("tag_ids") or [],
        scope=payload.get("tag_scope") or "all",
        slide=slide,
        survey_question=survey_question,
        user=user,
    )
