"""Helpers for wall posts (polls, events, typed create)."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from api.models import (
    BoardPollOption,
    BoardPollVote,
    BoardPost,
    PersonalBoardPollOption,
    PersonalBoardPollVote,
    PersonalBoardPost,
    WallPostType,
)

VALID_POST_TYPES = {c.value for c in WallPostType}


def _parse_dt(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise ValidationError({"detail": f"Invalid datetime: {value}"})
    return parsed


def normalize_wall_create_data(data: dict) -> dict:
    post_type = (data.get("post_type") or WallPostType.POST).strip().lower()
    if post_type not in VALID_POST_TYPES:
        raise ValidationError({"post_type": "Unsupported post type."})

    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    options = data.get("poll_options") or []
    if isinstance(options, str):
        options = [options]

    cleaned_options = []
    for raw in options:
        text = (raw if isinstance(raw, str) else str(raw or "")).strip()
        if text:
            cleaned_options.append(text[:200])

    event_starts_at = _parse_dt(data.get("event_starts_at"))
    event_ends_at = _parse_dt(data.get("event_ends_at"))
    event_location = (data.get("event_location") or "").strip()[:255]

    if post_type == WallPostType.POST:
        if not body:
            raise ValidationError({"body": "Write something to post."})
    elif post_type == WallPostType.QUESTION:
        if not body:
            raise ValidationError({"body": "Enter your question."})
    elif post_type == WallPostType.POLL:
        if not body:
            raise ValidationError({"body": "Enter the poll question."})
        if len(cleaned_options) < 2:
            raise ValidationError({"poll_options": "Add at least two poll options."})
        if len(cleaned_options) > 8:
            raise ValidationError({"poll_options": "At most 8 poll options."})
    elif post_type == WallPostType.EVENT:
        if not title:
            raise ValidationError({"title": "Event title is required."})
        if not event_starts_at:
            raise ValidationError({"event_starts_at": "Event start is required."})
    elif post_type == WallPostType.MEETING:
        raise ValidationError(
            {"post_type": "Meeting posts are created when a meeting is scheduled."}
        )

    return {
        "post_type": post_type,
        "title": title,
        "body": body,
        "poll_options": cleaned_options,
        "event_starts_at": event_starts_at,
        "event_ends_at": event_ends_at,
        "event_location": event_location,
    }


@transaction.atomic
def create_org_wall_post(*, board, author, data: dict) -> BoardPost:
    from api.usage_service import consume_board_post

    fields = normalize_wall_create_data(data)
    options = fields.pop("poll_options")
    consume_board_post(board.organization)
    post = BoardPost.objects.create(board=board, author=author, **fields)
    if post.post_type == WallPostType.POLL:
        BoardPollOption.objects.bulk_create(
            [
                BoardPollOption(post=post, text=text, sort_order=i)
                for i, text in enumerate(options)
            ]
        )
    return post


@transaction.atomic
def create_personal_wall_post(*, board, data: dict) -> PersonalBoardPost:
    fields = normalize_wall_create_data(data)
    options = fields.pop("poll_options")
    post = PersonalBoardPost.objects.create(board=board, **fields)
    if post.post_type == WallPostType.POLL:
        PersonalBoardPollOption.objects.bulk_create(
            [
                PersonalBoardPollOption(post=post, text=text, sort_order=i)
                for i, text in enumerate(options)
            ]
        )
    return post


def serialize_org_poll(post: BoardPost, user: User | None) -> dict | None:
    if post.post_type != WallPostType.POLL:
        return None
    options = list(post.poll_options.all())
    votes = list(post.poll_votes.select_related("option").all())
    counts = {opt.id: 0 for opt in options}
    viewer_option_id = None
    for vote in votes:
        counts[vote.option_id] = counts.get(vote.option_id, 0) + 1
        if user and user.is_authenticated and vote.user_id == user.id:
            viewer_option_id = vote.option_id
    total = len(votes)
    return {
        "total_votes": total,
        "viewer_option_id": viewer_option_id,
        "options": [
            {
                "id": opt.id,
                "text": opt.text,
                "vote_count": counts.get(opt.id, 0),
                "percent": round((counts.get(opt.id, 0) / total) * 100) if total else 0,
            }
            for opt in options
        ],
    }


def serialize_personal_poll(post: PersonalBoardPost, user: User | None) -> dict | None:
    if post.post_type != WallPostType.POLL:
        return None
    options = list(post.poll_options.all())
    votes = list(post.poll_votes.select_related("option").all())
    counts = {opt.id: 0 for opt in options}
    viewer_option_id = None
    for vote in votes:
        counts[vote.option_id] = counts.get(vote.option_id, 0) + 1
        if user and user.is_authenticated and vote.user_id == user.id:
            viewer_option_id = vote.option_id
    total = len(votes)
    return {
        "total_votes": total,
        "viewer_option_id": viewer_option_id,
        "options": [
            {
                "id": opt.id,
                "text": opt.text,
                "vote_count": counts.get(opt.id, 0),
                "percent": round((counts.get(opt.id, 0) / total) * 100) if total else 0,
            }
            for opt in options
        ],
    }


@transaction.atomic
def vote_org_poll(*, post: BoardPost, user: User, option_id: int) -> BoardPost:
    if post.post_type != WallPostType.POLL:
        raise ValidationError({"detail": "This post is not a poll."})
    option = BoardPollOption.objects.filter(post=post, pk=option_id).first()
    if not option:
        raise ValidationError({"option_id": "Invalid poll option."})
    BoardPollVote.objects.update_or_create(
        post=post, user=user, defaults={"option": option}
    )
    return post


@transaction.atomic
def vote_personal_poll(
    *, post: PersonalBoardPost, user: User, option_id: int
) -> PersonalBoardPost:
    if post.post_type != WallPostType.POLL:
        raise ValidationError({"detail": "This post is not a poll."})
    option = PersonalBoardPollOption.objects.filter(post=post, pk=option_id).first()
    if not option:
        raise ValidationError({"option_id": "Invalid poll option."})
    PersonalBoardPollVote.objects.update_or_create(
        post=post, user=user, defaults={"option": option}
    )
    return post
