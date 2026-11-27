"""Parse North Carolina voter extracts and compare them by NCID."""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from api.models import VoterFile, VoterRecord

# Newest ready file stays queryable. The previous ready file stays so a new
# statewide extract can still be compared with the one it replaced.
KEEP_READY_FILES = 2

HEADER_ALIASES = {
    "ncid": "ncid",
    "county_desc": "county",
    "county": "county",
    "county_id": "county_id",
    "last_name": "last_name",
    "first_name": "first_name",
    "middle_name": "middle_name",
    "res_street_address": "address",
    "address": "address",
    "res_city_desc": "city",
    "city": "city",
    "zip_code": "zip_code",
    "zip": "zip_code",
    "voter_status_desc": "status",
    "status_cd": "status",
    "status": "status",
    "party_cd": "party",
    "party": "party",
}

COMPARE_FIELDS = ("last_name", "first_name", "address", "status", "party")
QUERY_FIELDS = (
    "county",
    "county_id",
    "ncid",
    "last_name",
    "first_name",
    "middle_name",
    "address",
    "city",
    "zip_code",
    "status",
    "party",
)


def _open_text(path: Path):
    if path.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(path)
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith((".txt", ".tsv", ".csv")) and not name.endswith("/")
        ]
        if not names:
            raise ValueError("The zip file does not contain a voter text file.")
        raw = archive.read(names[0])
        return io.StringIO(raw.decode("utf-8-sig", errors="replace"))
    return path.open("r", encoding="utf-8-sig", errors="replace", newline="")


def _reader(text_file):
    sample = text_file.read(4096)
    text_file.seek(0)
    delimiter = "\t" if sample.count("\t") >= sample.count(",") else ","
    reader = csv.DictReader(text_file, delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("The file has no header row.")
    mapping = {}
    for header in reader.fieldnames:
        key = (header or "").strip().strip('"').lower()
        if key in HEADER_ALIASES:
            mapping[header] = HEADER_ALIASES[key]
    if "ncid" not in mapping.values():
        raise ValueError(
            "Unrecognized voter file. Expected an ncid column "
            "(North Carolina statewide extract)."
        )
    return reader, mapping


def _line_hash(row: dict) -> str:
    parts = [row.get("ncid", "")]
    parts.extend(row.get(field, "") for field in COMPARE_FIELDS)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


FIELD_LIMITS = {
    "county": 80,
    "county_id": 16,
    "ncid": 32,
    "last_name": 80,
    "first_name": 80,
    "middle_name": 80,
    "address": 200,
    "city": 80,
    "zip_code": 16,
    "status": 40,
    "party": 16,
}


def _remember_skip(samples: list, message: str) -> None:
    if len(samples) < 20:
        samples.append(message[:240])


def _row_from_raw(raw, mapping, line_number: int):
    row = {field: "" for field in QUERY_FIELDS}
    for header, field in mapping.items():
        value = (raw.get(header) or "").strip()
        if value and not row[field]:
            row[field] = value
    if not row["ncid"]:
        raise ValueError(f"Line {line_number}: missing ncid")
    for field, limit in FIELD_LIMITS.items():
        if len(row[field]) > limit:
            raise ValueError(f"Line {line_number}: {field} is longer than {limit} characters")
    row["line_hash"] = _line_hash(row)
    return row


def _save_batch(voter_file, batch, samples):
    try:
        VoterRecord.objects.bulk_create(batch)
        return len(batch), 0
    except Exception:
        stored = 0
        skipped = 0
        for record in batch:
            try:
                record.save()
                stored += 1
            except Exception as exc:
                skipped += 1
                _remember_skip(samples, f"{record.ncid or 'row'}: {exc}")
        return stored, skipped


def _checkpoint(voter_file, stored, skipped, samples):
    voter_file.row_count = stored
    voter_file.rows_skipped = skipped
    voter_file.skip_samples = samples
    voter_file.save(update_fields=["row_count", "rows_skipped", "skip_samples"])


def parse_voter_file(file_id: int) -> None:
    voter_file = VoterFile.objects.get(pk=file_id)
    voter_file.status = VoterFile.Status.PARSING
    voter_file.error = ""
    voter_file.row_count = 0
    voter_file.rows_skipped = 0
    voter_file.skip_samples = []
    voter_file.save(update_fields=["status", "error", "row_count", "rows_skipped", "skip_samples"])
    voter_file.records.all().delete()
    stored = 0
    skipped = 0
    samples = []
    try:
        path = Path(voter_file.stored_path)
        text_file = _open_text(path)
        try:
            reader, mapping = _reader(text_file)
            batch = []
            for line_number, raw in enumerate(reader, start=2):
                try:
                    row = _row_from_raw(raw, mapping, line_number)
                except Exception as exc:
                    skipped += 1
                    _remember_skip(samples, str(exc))
                    continue
                batch.append(VoterRecord(voter_file=voter_file, **row))
                if len(batch) >= 1000:
                    added, bad = _save_batch(voter_file, batch, samples)
                    stored += added
                    skipped += bad
                    batch = []
                    _checkpoint(voter_file, stored, skipped, samples)
            if batch:
                added, bad = _save_batch(voter_file, batch, samples)
                stored += added
                skipped += bad
        finally:
            text_file.close()
    except Exception as exc:
        voter_file.status = VoterFile.Status.FAILED
        voter_file.error = str(exc)
        voter_file.row_count = stored
        voter_file.rows_skipped = skipped
        voter_file.skip_samples = samples
        voter_file.save(update_fields=["status", "error", "row_count", "rows_skipped", "skip_samples"])
        return
    if stored == 0:
        voter_file.status = VoterFile.Status.FAILED
        voter_file.error = "No voter rows could be stored."
        voter_file.row_count = 0
        voter_file.rows_skipped = skipped
        voter_file.skip_samples = samples
        voter_file.save(update_fields=["status", "error", "row_count", "rows_skipped", "skip_samples"])
        return
    voter_file.row_count = stored
    voter_file.rows_skipped = skipped
    voter_file.skip_samples = samples
    voter_file.status = VoterFile.Status.READY
    voter_file.parsed_at = timezone.now()
    voter_file.error = ""
    voter_file.save(
        update_fields=["row_count", "rows_skipped", "skip_samples", "status", "parsed_at", "error"]
    )
    retain_voter_files(voter_file)


def retain_voter_files(voter_file: VoterFile) -> int:
    """Delete ready and failed copies beyond the two newest ready files."""
    if voter_file.source == VoterFile.Source.COMPARISON_LIST:
        return 0
    ready = VoterFile.objects.filter(source=voter_file.source, status=VoterFile.Status.READY)
    if voter_file.source == VoterFile.Source.OFFICIAL:
        ready = ready.filter(install__isnull=True)
    else:
        ready = ready.filter(install_id=voter_file.install_id)
    keep_ids = list(ready.order_by("-parsed_at", "-id").values_list("id", flat=True)[:KEEP_READY_FILES])
    stale = VoterFile.objects.filter(source=voter_file.source).exclude(pk__in=keep_ids).exclude(
        status__in=(VoterFile.Status.QUEUED, VoterFile.Status.PARSING)
    )
    if voter_file.source == VoterFile.Source.OFFICIAL:
        stale = stale.filter(install__isnull=True)
    else:
        stale = stale.filter(install_id=voter_file.install_id)
    root = (Path(settings.BASE_DIR) / "private_voter_files").resolve()
    removed = 0
    for old in list(stale):
        stored = Path(old.stored_path) if old.stored_path else None
        old.delete()
        if stored and stored.is_file():
            try:
                stored.resolve().relative_to(root)
            except ValueError:
                pass
            else:
                stored.unlink()
        removed += 1
    if voter_file.source == VoterFile.Source.OFFICIAL:
        newest = (
            VoterFile.objects.filter(
                source=VoterFile.Source.OFFICIAL,
                status=VoterFile.Status.READY,
                install__isnull=True,
            )
            .order_by("-parsed_at", "-id")
            .first()
        )
        if newest is not None:
            VoterFile.objects.filter(is_current_official=True).exclude(pk=newest.pk).update(
                is_current_official=False
            )
            if not newest.is_current_official:
                newest.is_current_official = True
                newest.save(update_fields=["is_current_official"])
    return removed


def parse_comparison_list(file_id: int) -> None:
    """A short CSV matched by NCID, or by name, address, and county."""
    voter_file = VoterFile.objects.get(pk=file_id)
    voter_file.status = VoterFile.Status.PARSING
    voter_file.error = ""
    voter_file.save(update_fields=["status", "error"])
    voter_file.records.all().delete()
    try:
        path = Path(voter_file.stored_path)
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("The comparison list has no header row.")
            fields = {(name or "").strip().lower(): name for name in reader.fieldnames}
            has_ncid = "ncid" in fields
            has_name = "last_name" in fields and "first_name" in fields
            if not has_ncid and not has_name:
                raise ValueError(
                    "A comparison list needs an ncid column, or last_name and first_name."
                )
            batch = []
            count = 0
            for raw in reader:
                def cell(name):
                    header = fields.get(name)
                    return (raw.get(header) or "").strip() if header else ""

                row = {field: "" for field in QUERY_FIELDS}
                row["ncid"] = cell("ncid")
                row["last_name"] = cell("last_name")
                row["first_name"] = cell("first_name")
                row["address"] = cell("address") or cell("res_street_address")
                row["county"] = cell("county") or cell("county_desc")
                if not row["ncid"] and not row["last_name"]:
                    continue
                row["line_hash"] = _line_hash(row)
                batch.append(VoterRecord(voter_file=voter_file, **row))
                count += 1
            if batch:
                VoterRecord.objects.bulk_create(batch)
    except Exception as exc:
        voter_file.status = VoterFile.Status.FAILED
        voter_file.error = str(exc)
        voter_file.save(update_fields=["status", "error"])
        return
    voter_file.row_count = count
    voter_file.status = VoterFile.Status.READY
    voter_file.parsed_at = timezone.now()
    voter_file.save(update_fields=["row_count", "status", "parsed_at"])


def _index(voter_file: VoterFile, county: str = ""):
    qs = voter_file.records.all()
    if county:
        qs = qs.filter(county__iexact=county)
    indexed = {}
    for record in qs.iterator():
        if record.ncid:
            indexed[record.ncid] = record
    return indexed


def compare_files(file_a: VoterFile, file_b: VoterFile, county: str = "", sample_limit: int = 200):
    left = _index(file_a, county)
    right = _index(file_b, county)
    only_a = []
    only_b = []
    changed = []
    for ncid, record in left.items():
        other = right.get(ncid)
        if other is None:
            only_a.append(record)
        elif record.line_hash != other.line_hash:
            changed.append((record, other))
    for ncid, record in right.items():
        if ncid not in left:
            only_b.append(record)

    def brief(record: VoterRecord):
        return {
            "ncid": record.ncid,
            "county": record.county,
            "last_name": record.last_name,
            "first_name": record.first_name,
            "address": record.address,
            "status": record.status,
            "party": record.party,
        }

    return {
        "only_in_a_count": len(only_a),
        "only_in_b_count": len(only_b),
        "changed_count": len(changed),
        "only_in_a": [brief(row) for row in only_a[:sample_limit]],
        "only_in_b": [brief(row) for row in only_b[:sample_limit]],
        "changed": [
            {"ncid": left_row.ncid, "before": brief(left_row), "after": brief(right_row)}
            for left_row, right_row in changed[:sample_limit]
        ],
        "only_in_a_rows": only_a,
        "only_in_b_rows": only_b,
    }


def match_list(voter_file: VoterFile, comparison: VoterFile):
    by_ncid = {}
    by_name = {}
    for record in voter_file.records.iterator():
        if record.ncid:
            by_ncid[record.ncid.upper()] = record
        key = (
            record.last_name.strip().upper(),
            record.first_name.strip().upper(),
            record.address.strip().upper(),
            record.county.strip().upper(),
        )
        by_name.setdefault(key, []).append(record)

    matched = []
    unmatched = []
    ambiguous = []
    for item in comparison.records.all():
        if item.ncid:
            found = by_ncid.get(item.ncid.upper())
            if found:
                matched.append({"list": _public_row(item), "voter": _public_row(found)})
            else:
                unmatched.append(_public_row(item))
            continue
        key = (
            item.last_name.strip().upper(),
            item.first_name.strip().upper(),
            item.address.strip().upper(),
            item.county.strip().upper(),
        )
        hits = by_name.get(key) or []
        if len(hits) == 1:
            matched.append({"list": _public_row(item), "voter": _public_row(hits[0])})
        elif len(hits) > 1:
            ambiguous.append(_public_row(item))
        else:
            unmatched.append(_public_row(item))
    return {
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "ambiguous_count": len(ambiguous),
        "matched": matched[:200],
        "unmatched": unmatched[:200],
        "ambiguous": ambiguous[:200],
    }


def _public_row(record: VoterRecord):
    return {field: getattr(record, field) for field in QUERY_FIELDS}
