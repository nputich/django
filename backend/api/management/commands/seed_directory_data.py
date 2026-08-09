"""Seed geographic reference data and the full org directory taxonomy."""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from api.directory_taxonomy import DIRECTORY_TAXONOMY
from api.models import GeographicArea, OrgCategory

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FIPS_CSV = DATA_DIR / "us_county_fips.csv"

STARTER_COUNTRIES = [
    ("United States", "us", "US", 0),
    ("Canada", "ca", "CA", 10),
    ("Mexico", "mx", "MX", 20),
    ("United Kingdom", "gb", "GB", 30),
    ("Australia", "au", "AU", 40),
]

USPS_BY_STATE_FIPS = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
    "60": "AS",
    "66": "GU",
    "69": "MP",
    "72": "PR",
    "78": "VI",
}


def _unique_slug(base: str, used: set[str]) -> str:
    slug = slugify(base) or "area"
    candidate = slug
    i = 2
    while candidate in used:
        candidate = f"{slug}-{i}"
        i += 1
    used.add(candidate)
    return candidate


def _title_state_name(name: str) -> str:
    specials = {"DISTRICT OF COLUMBIA": "District of Columbia"}
    upper = name.strip().upper()
    if upper in specials:
        return specials[upper]
    return " ".join(part.capitalize() for part in name.strip().split())


class Command(BaseCommand):
    help = "Seed GeographicArea (US + starter countries) and OrgCategory taxonomy."

    def add_arguments(self, parser):
        parser.add_argument("--skip-geo", action="store_true")
        parser.add_argument("--skip-categories", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["skip_categories"]:
            self._seed_categories()
        if not options["skip_geo"]:
            self._seed_geo()
        self.stdout.write(self.style.SUCCESS("Directory reference data seeded."))

    def _seed_categories(self):
        for index, entry in enumerate(DIRECTORY_TAXONOMY):
            category, _ = OrgCategory.objects.update_or_create(
                parent=None,
                slug=entry["slug"],
                defaults={
                    "name": entry["name"],
                    "sort_order": index,
                    "is_active": True,
                },
            )
            for sub_index, (name, slug) in enumerate(entry["subcategories"]):
                OrgCategory.objects.update_or_create(
                    parent=category,
                    slug=slug,
                    defaults={
                        "name": name,
                        "sort_order": sub_index,
                        "is_active": True,
                    },
                )
        self.stdout.write(
            f"Categories: {OrgCategory.objects.filter(parent__isnull=True).count()} "
            f"top-level, {OrgCategory.objects.filter(parent__isnull=False).count()} subcategories"
        )

    def _seed_geo(self):
        if not FIPS_CSV.is_file():
            raise FileNotFoundError(f"Missing FIPS data file: {FIPS_CSV}")

        for name, slug, code, sort_order in STARTER_COUNTRIES:
            GeographicArea.objects.update_or_create(
                parent=None,
                slug=slug,
                defaults={
                    "name": name,
                    "area_type": GeographicArea.AreaType.COUNTRY,
                    "country_code": code,
                    "external_code": code,
                    "is_active": True,
                    "sort_order": sort_order,
                },
            )
        us = GeographicArea.objects.get(
            parent=None, slug="us", area_type=GeographicArea.AreaType.COUNTRY
        )

        rows = list(csv.DictReader(FIPS_CSV.open(encoding="utf-8")))
        state_by_fips: dict[str, str] = {}
        county_rows: list[tuple[str, str, str]] = []

        for row in rows:
            fips = (row.get("fips") or "").strip()
            name = (row.get("name") or "").strip()
            state = (row.get("state") or "").strip().upper()
            if not fips or not name:
                continue
            try:
                fips_int = int(fips)
            except ValueError:
                continue
            if name.upper() == "UNITED STATES":
                continue
            if state == "NA" and fips_int % 1000 == 0:
                state_by_fips[f"{fips_int // 1000:02d}"] = _title_state_name(name)
            elif state and state != "NA":
                county_rows.append((f"{fips_int:05d}", name, state))

        used_state_slugs: set[str] = set()
        admin1_by_abbr: dict[str, GeographicArea] = {}
        for state_fips, name in sorted(state_by_fips.items()):
            abbr = USPS_BY_STATE_FIPS.get(state_fips)
            if not abbr:
                continue
            existing = GeographicArea.objects.filter(
                parent=us,
                area_type=GeographicArea.AreaType.ADMIN1,
                external_code=state_fips,
            ).first()
            if existing:
                area = existing
                area.name = name
                area.is_active = True
                area.sort_order = int(state_fips)
                area.save()
                used_state_slugs.add(area.slug)
            else:
                slug = _unique_slug(name, used_state_slugs)
                area = GeographicArea.objects.create(
                    parent=us,
                    slug=slug,
                    name=name,
                    area_type=GeographicArea.AreaType.ADMIN1,
                    country_code="US",
                    external_code=state_fips,
                    is_active=True,
                    sort_order=int(state_fips),
                )
            admin1_by_abbr[abbr] = area

        for fips, name, abbr in county_rows:
            parent = admin1_by_abbr.get(abbr)
            if not parent:
                continue
            existing = GeographicArea.objects.filter(
                area_type=GeographicArea.AreaType.ADMIN2,
                external_code=fips,
            ).first()
            if existing:
                existing.name = name
                existing.parent = parent
                existing.country_code = "US"
                existing.is_active = True
                existing.sort_order = int(fips)
                existing.save()
                continue

            used = set(
                GeographicArea.objects.filter(
                    parent=parent, area_type=GeographicArea.AreaType.ADMIN2
                ).values_list("slug", flat=True)
            )
            slug = _unique_slug(name, used)
            GeographicArea.objects.create(
                parent=parent,
                slug=slug,
                name=name,
                area_type=GeographicArea.AreaType.ADMIN2,
                country_code="US",
                external_code=fips,
                is_active=True,
                sort_order=int(fips),
            )

        self.stdout.write(
            f"Geo: {GeographicArea.objects.filter(area_type='country').count()} countries, "
            f"{GeographicArea.objects.filter(area_type='admin1').count()} admin1, "
            f"{GeographicArea.objects.filter(area_type='admin2').count()} admin2"
        )
