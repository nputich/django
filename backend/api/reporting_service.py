"""
Cross-meeting / cross-survey reporting for an organization.

Groups responses by question identity (``question_key``) and by tag, over a
date range, and returns per-month series plus choice buckets. Designed for
"what did people tell us about X over the last six months?" questions.
"""

from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import (
    MeetingResponse,
    MeetingSlide,
    Organization,
    QuestionTagLink,
    SurveyAnswer,
    SurveyQuestion,
)
from .question_tags import available_tags, serialize_tag

CHOICE_FORMATS = {
    MeetingSlide.QuestionFormat.SINGLE_CHOICE,
    MeetingSlide.QuestionFormat.MULTI_CHOICE,
}


@dataclass
class ReportFilters:
    start: datetime | None = None
    end: datetime | None = None
    tag_ids: set[int] = field(default_factory=set)
    query: str = ""
    source: str = "all"  # all | meetings | surveys


def parse_filters(params) -> ReportFilters:
    def _date(raw, end_of_day=False):
        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None
        t = time.max if end_of_day else time.min
        return timezone.make_aware(datetime.combine(d, t))

    tag_ids = set()
    for chunk in (params.get("tags") or "").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            tag_ids.add(int(chunk))
    source = (params.get("source") or "all").lower()
    if source not in ("all", "meetings", "surveys"):
        source = "all"
    start = _date(params.get("from"))
    end = _date(params.get("to"), end_of_day=True)
    if start is None and end is None:
        # Default: trailing 6 months.
        end = timezone.now()
        start = end - timedelta(days=182)
    return ReportFilters(
        start=start,
        end=end,
        tag_ids=tag_ids,
        query=(params.get("q") or "").strip(),
        source=source,
    )


def _month(dt) -> str:
    local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return local.strftime("%Y-%m")


def _org_wide_tag_map(organization: Organization) -> dict[str, set[int]]:
    result: dict[str, set[int]] = defaultdict(set)
    for key, tag_id in QuestionTagLink.objects.filter(
        organization=organization, slide__isnull=True, survey_question__isnull=True
    ).values_list("question_key", "tag_id"):
        result[key].add(tag_id)
    return result


def _per_use_tag_map(organization: Organization) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    slide_tags: dict[int, set[int]] = defaultdict(set)
    sq_tags: dict[int, set[int]] = defaultdict(set)
    for slide_id, sq_id, tag_id in QuestionTagLink.objects.filter(organization=organization).exclude(
        slide__isnull=True, survey_question__isnull=True
    ).values_list("slide_id", "survey_question_id", "tag_id"):
        if slide_id:
            slide_tags[slide_id].add(tag_id)
        if sq_id:
            sq_tags[sq_id].add(tag_id)
    return slide_tags, sq_tags


def build_report(organization: Organization, filters: ReportFilters) -> dict:
    org_wide = _org_wide_tag_map(organization)
    slide_tags, sq_tags = _per_use_tag_map(organization)
    tag_lookup = {t.id: t for t in available_tags(organization)}

    # ---- collect responses --------------------------------------------------
    groups: dict[str, dict] = {}

    def group_for(key: str, text: str, fmt: str, choices: list) -> dict:
        g = groups.get(key)
        if g is None:
            g = groups[key] = {
                "question_key": key,
                "text": text,
                "formats": set(),
                "choices": list(choices or []),
                "meetings": set(),
                "surveys": set(),
                "responses": 0,
                "participants": set(),
                "months": Counter(),
                "choice_counts": Counter(),
                "issue_counts": Counter(),
                "tag_ids": set(org_wide.get(key, set())),
                "samples": [],
            }
        if fmt:
            g["formats"].add(fmt)
        for c in choices or []:
            if c not in g["choices"]:
                g["choices"].append(c)
        return g

    if filters.source in ("all", "meetings"):
        responses = (
            MeetingResponse.objects.filter(
                meeting__organization=organization,
                slide__isnull=False,
                slide__slide_type__in=MeetingSlide.QUESTION_TYPES,
            )
            .exclude(slide__question_key="")
            .select_related("slide")
            .order_by("-created_at")
        )
        if filters.start:
            responses = responses.filter(created_at__gte=filters.start)
        if filters.end:
            responses = responses.filter(created_at__lte=filters.end)
        if filters.query:
            responses = responses.filter(slide__prompt__icontains=filters.query) | responses.filter(
                slide__title__icontains=filters.query
            )
        for r in responses.iterator(chunk_size=2000):
            s = r.slide
            g = group_for(s.question_key, s.prompt or s.title, s.question_format or s.slide_type, s.choices)
            g["tag_ids"] |= slide_tags.get(s.id, set())
            g["meetings"].add(r.meeting_id)
            g["responses"] += 1
            if r.participant_id:
                g["participants"].add(str(r.participant_id))
            g["months"][_month(r.created_at)] += 1
            for opt in r.selected_options or []:
                g["choice_counts"][str(opt)] += 1
            if s.slide_type == MeetingSlide.SlideType.POLITICAL_ISSUE_CARD:
                g["issue_counts"][r.major_issue or "Unclassified"] += 1
            if not r.selected_options and r.raw_response and len(g["samples"]) < 8:
                g["samples"].append({"text": r.raw_response[:300], "at": r.created_at, "source": "meeting"})

    if filters.source in ("all", "surveys"):
        answers = (
            SurveyAnswer.objects.filter(survey__organization=organization)
            .exclude(question__question_key="")
            .select_related("question")
            .order_by("-created_at")
        )
        if filters.start:
            answers = answers.filter(created_at__gte=filters.start)
        if filters.end:
            answers = answers.filter(created_at__lte=filters.end)
        if filters.query:
            answers = answers.filter(question__text__icontains=filters.query)
        for a in answers.iterator(chunk_size=2000):
            q = a.question
            fmt = "single_choice" if q.question_type == SurveyQuestion.QuestionType.CHOICE else "text"
            g = group_for(q.question_key, q.text, fmt, q.choices)
            g["tag_ids"] |= sq_tags.get(q.id, set())
            g["surveys"].add(a.survey_id)
            g["responses"] += 1
            g["participants"].add(f"s:{a.response_session}")
            g["months"][_month(a.created_at)] += 1
            if q.question_type == SurveyQuestion.QuestionType.CHOICE:
                g["choice_counts"][a.value] += 1
            elif a.value and len(g["samples"]) < 8:
                g["samples"].append({"text": a.value[:300], "at": a.created_at, "source": "survey"})

    # ---- tag filter ----------------------------------------------------------
    if filters.tag_ids:
        groups = {k: g for k, g in groups.items() if g["tag_ids"] & filters.tag_ids}

    # ---- months axis ---------------------------------------------------------
    all_months: set[str] = set()
    for g in groups.values():
        all_months |= set(g["months"])
    months = sorted(all_months)

    def series(counter: Counter) -> list[dict]:
        return [{"month": m, "responses": counter.get(m, 0)} for m in months]

    # ---- serialize questions -------------------------------------------------
    questions = []
    for g in sorted(groups.values(), key=lambda x: (-x["responses"], x["text"])):
        ordered = OrderedDict()
        for c in g["choices"]:
            ordered[str(c)] = g["choice_counts"].get(str(c), 0)
        for c, n in g["choice_counts"].items():
            ordered.setdefault(c, n)
        questions.append(
            {
                "question_key": g["question_key"],
                "text": g["text"],
                "formats": sorted(g["formats"]),
                "times_asked": {"meetings": len(g["meetings"]), "surveys": len(g["surveys"])},
                "responses": g["responses"],
                "participants": len(g["participants"]),
                "tags": [serialize_tag(tag_lookup[t]) for t in sorted(g["tag_ids"]) if t in tag_lookup],
                "months": series(g["months"]),
                "choice_counts": ordered if ordered else None,
                "issue_counts": dict(g["issue_counts"].most_common()) if g["issue_counts"] else None,
                "samples": g["samples"],
            }
        )

    # ---- tag rollup ----------------------------------------------------------
    tag_rows: dict[int, dict] = {}
    for g in groups.values():
        for tid in g["tag_ids"]:
            if tid not in tag_lookup:
                continue
            row = tag_rows.setdefault(
                tid, {"tag": serialize_tag(tag_lookup[tid]), "questions": 0, "responses": 0, "months": Counter()}
            )
            row["questions"] += 1
            row["responses"] += g["responses"]
            row["months"].update(g["months"])
    tags = [
        {**row, "months": series(row["months"])}
        for row in sorted(tag_rows.values(), key=lambda r: (-r["responses"], r["tag"]["label"]))
    ]

    return {
        "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
        "filters": {
            "from": filters.start.date().isoformat() if filters.start else None,
            "to": filters.end.date().isoformat() if filters.end else None,
            "tags": sorted(filters.tag_ids),
            "q": filters.query,
            "source": filters.source,
        },
        "months": months,
        "totals": {
            "questions": len(questions),
            "responses": sum(q["responses"] for q in questions),
            "meetings": len({m for g in groups.values() for m in g["meetings"]}),
            "surveys": len({s for g in groups.values() for s in g["surveys"]}),
        },
        "questions": questions,
        "tags": tags,
    }


REPORT_CSV_COLUMNS = [
    "question_text",
    "question_key",
    "tags",
    "formats",
    "meetings_asked",
    "surveys_asked",
    "responses",
    "participants",
    "month",
    "month_responses",
    "bucket",
    "bucket_count",
]


def report_csv_rows(report: dict) -> list[dict]:
    rows = []
    for q in report["questions"]:
        base = {
            "question_text": q["text"],
            "question_key": q["question_key"],
            "tags": "; ".join(t["label"] for t in q["tags"]),
            "formats": "; ".join(q["formats"]),
            "meetings_asked": q["times_asked"]["meetings"],
            "surveys_asked": q["times_asked"]["surveys"],
            "responses": q["responses"],
            "participants": q["participants"],
            "month": "",
            "month_responses": "",
            "bucket": "",
            "bucket_count": "",
        }
        rows.append(dict(base))
        for m in q["months"]:
            if m["responses"]:
                rows.append({**base, "month": m["month"], "month_responses": m["responses"]})
        for bucket, n in (q["choice_counts"] or {}).items():
            rows.append({**base, "bucket": bucket, "bucket_count": n})
        for bucket, n in (q["issue_counts"] or {}).items():
            rows.append({**base, "bucket": f"issue:{bucket}", "bucket_count": n})
    return rows
