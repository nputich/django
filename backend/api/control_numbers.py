"""Stable CommuniBetter IDs for users (U-) and organizations (O-).

Separate sequences so people and orgs never share an allocation pool.
Numbers grow from 1; presentation adds the U-/O- prefix and optional grouping.
"""

from __future__ import annotations

import re

from django.db import connection, transaction

USER_SEQ = "communibetter_user_control_number_seq"
ORG_SEQ = "communibetter_org_control_number_seq"

_CODE_RE = re.compile(
    r"^\s*([UuOo])\s*[-]?\s*(\d+)\s*$"
)
_DIGITS_RE = re.compile(r"^\s*(\d+)\s*$")


def format_user_control_number(n: int | None) -> str | None:
    if n is None:
        return None
    return f"U-{n}"


def format_org_control_number(n: int | None) -> str | None:
    if n is None:
        return None
    return f"O-{n}"


def parse_control_code(raw: str | None) -> tuple[str | None, int | None]:
    """Return (kind, number) where kind is 'user' | 'org' | None.

    Accepts: U-42, u42, O-7, 42 (digits-only → kind None, number set).
    """
    if not raw:
        return None, None
    text = str(raw).strip()
    m = _CODE_RE.match(text)
    if m:
        kind = "user" if m.group(1).upper() == "U" else "org"
        return kind, int(m.group(2))
    m = _DIGITS_RE.match(text)
    if m:
        return None, int(m.group(1))
    return None, None


def _next_val(sequence_name: str) -> int:
    if connection.vendor != "postgresql":
        from api.models import Organization, UserProfile

        if sequence_name == USER_SEQ:
            current = (
                UserProfile.objects.exclude(control_number__isnull=True)
                .order_by("-control_number")
                .values_list("control_number", flat=True)
                .first()
            )
        else:
            current = (
                Organization.objects.exclude(control_number__isnull=True)
                .order_by("-control_number")
                .values_list("control_number", flat=True)
                .first()
            )
        return int(current or 0) + 1
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [sequence_name])
        return int(cursor.fetchone()[0])


@transaction.atomic
def allocate_user_control_number() -> int:
    return _next_val(USER_SEQ)


@transaction.atomic
def allocate_org_control_number() -> int:
    return _next_val(ORG_SEQ)


def ensure_user_control_number(profile) -> int:
    # 0 is a valid CommuniBetter ID (U-0) — never treat it as missing.
    if profile.control_number is not None:
        return profile.control_number
    with transaction.atomic():
        # Re-read under lock if another writer raced.
        from api.models import UserProfile

        locked = (
            UserProfile.objects.select_for_update()
            .filter(pk=profile.pk)
            .first()
        )
        if locked is None:
            return allocate_user_control_number()
        if locked.control_number is not None:
            profile.control_number = locked.control_number
            return locked.control_number
        n = allocate_user_control_number()
        UserProfile.objects.filter(pk=locked.pk, control_number__isnull=True).update(
            control_number=n
        )
        profile.control_number = n
        return n


def ensure_org_control_number(organization) -> int:
    # 0 is a valid CommuniBetter ID (O-0) — never treat it as missing.
    if organization.control_number is not None:
        return organization.control_number
    with transaction.atomic():
        from api.models import Organization

        locked = (
            Organization.objects.select_for_update()
            .filter(pk=organization.pk)
            .first()
        )
        if locked is None:
            return allocate_org_control_number()
        if locked.control_number is not None:
            organization.control_number = locked.control_number
            return locked.control_number
        n = allocate_org_control_number()
        Organization.objects.filter(pk=locked.pk, control_number__isnull=True).update(
            control_number=n
        )
        organization.control_number = n
        return n
