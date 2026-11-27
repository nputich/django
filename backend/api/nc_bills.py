"""North Carolina General Assembly House and Senate bills."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, application/rss+xml, text/html"}
CHAMBERS = {"H": "house", "S": "senate"}


def _get(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read()
        charset = "utf-8"
        content_type = resp.headers.get("Content-Type") or ""
        if "windows-1252" in content_type.lower():
            charset = "cp1252"
        return raw.decode(charset, errors="replace"), content_type


def list_bills(session_year: int, chamber_code: str) -> list[dict]:
    body, _ctype = _get(f"https://webservices.ncleg.gov/AllBills/{session_year}")
    rows = json.loads(body)
    return [row for row in rows if (row.get("chamber") or "").upper() == chamber_code.upper()]


def bill_history(session_year: int, chamber_code: str, number: int) -> dict:
    citation = f"{chamber_code.upper()}{number}"
    body, _ctype = _get(
        f"https://webservices.ncleg.gov/BillHistory/{session_year}/{citation}/RSS"
    )
    root = ET.fromstring(body)
    channel = root.find("channel")
    title = (channel.findtext("title") or "").strip()
    link = (channel.findtext("link") or "").strip()
    short = title
    match = re.match(r"^[^-]+-\s*(.+?)\s*\(\d{4}", title)
    if match:
        short = match.group(1).strip().rstrip(".")
    items = channel.findall("item")
    latest = ""
    latest_date = None
    if items:
        latest = (items[-1].findtext("title") or "").strip()
        pub = items[-1].findtext("pubDate") or ""
        latest_date = _rss_date(pub)
    return {
        "session_year": session_year,
        "bill_type": chamber_code.lower(),
        "bill_number": number,
        "chamber": CHAMBERS[chamber_code.upper()],
        "title": short or title,
        "latest_action": latest,
        "latest_action_date": latest_date,
        "source_url": link or f"https://www.ncleg.gov/BillLookUp/{session_year}/{citation}",
    }


def bill_text(session_year: int, chamber_code: str, number: int, max_chars: int = 12000) -> str:
    folder = "House" if chamber_code.upper() == "H" else "Senate"
    prefix = chamber_code.upper()
    text = ""
    for version in range(0, 6):
        url = (
            f"https://www.ncleg.gov/Sessions/{session_year}/Bills/"
            f"{folder}/HTML/{prefix}{number}v{version}.html"
        )
        try:
            body, _ctype = _get(url)
        except urllib.error.HTTPError:
            if version == 0:
                continue
            break
        text = _visible_text(body)
    return text[:max_chars]


def _visible_text(html: str) -> str:
    without = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    without = re.sub(r"(?is)<[^>]+>", " ", without)
    return re.sub(r"\s+", " ", without).strip()


def _rss_date(value: str) -> date | None:
    match = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", value or "")
    if not match:
        return None
    months = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
    }
    month = months.get(match.group(2).title())
    if not month:
        return None
    return date(int(match.group(3)), month, int(match.group(1)))
