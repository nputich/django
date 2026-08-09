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
    ("Belize", "bz", "BZ", 21),
    ("Guatemala", "gt", "GT", 22),
    ("El Salvador", "sv", "SV", 23),
    ("Honduras", "hn", "HN", 24),
    ("Nicaragua", "ni", "NI", 25),
    ("Costa Rica", "cr", "CR", 26),
    ("Panama", "pa", "PA", 27),
    ("United Kingdom", "gb", "GB", 30),
    ("Australia", "au", "AU", 40),
]

# First administrative level (state / province / territory / nation) by country slug.
# US admin1 is loaded from FIPS; these cover the other starter countries.
ADMIN1_BY_COUNTRY: dict[str, list[tuple[str, str, str]]] = {
    # (name, slug, external_code)
    "ca": [
        ("Alberta", "alberta", "AB"),
        ("British Columbia", "british-columbia", "BC"),
        ("Manitoba", "manitoba", "MB"),
        ("New Brunswick", "new-brunswick", "NB"),
        ("Newfoundland and Labrador", "newfoundland-and-labrador", "NL"),
        ("Northwest Territories", "northwest-territories", "NT"),
        ("Nova Scotia", "nova-scotia", "NS"),
        ("Nunavut", "nunavut", "NU"),
        ("Ontario", "ontario", "ON"),
        ("Prince Edward Island", "prince-edward-island", "PE"),
        ("Quebec", "quebec", "QC"),
        ("Saskatchewan", "saskatchewan", "SK"),
        ("Yukon", "yukon", "YT"),
    ],
    "mx": [
        ("Aguascalientes", "aguascalientes", "AGU"),
        ("Baja California", "baja-california", "BCN"),
        ("Baja California Sur", "baja-california-sur", "BCS"),
        ("Campeche", "campeche", "CAM"),
        ("Chiapas", "chiapas", "CHP"),
        ("Chihuahua", "chihuahua", "CHH"),
        ("Mexico City", "mexico-city", "CMX"),
        ("Coahuila", "coahuila", "COA"),
        ("Colima", "colima", "COL"),
        ("Durango", "durango", "DUR"),
        ("Guanajuato", "guanajuato", "GUA"),
        ("Guerrero", "guerrero", "GRO"),
        ("Hidalgo", "hidalgo", "HID"),
        ("Jalisco", "jalisco", "JAL"),
        ("México", "mexico-state", "MEX"),
        ("Michoacán", "michoacan", "MIC"),
        ("Morelos", "morelos", "MOR"),
        ("Nayarit", "nayarit", "NAY"),
        ("Nuevo León", "nuevo-leon", "NLE"),
        ("Oaxaca", "oaxaca", "OAX"),
        ("Puebla", "puebla", "PUE"),
        ("Querétaro", "queretaro", "QUE"),
        ("Quintana Roo", "quintana-roo", "ROO"),
        ("San Luis Potosí", "san-luis-potosi", "SLP"),
        ("Sinaloa", "sinaloa", "SIN"),
        ("Sonora", "sonora", "SON"),
        ("Tabasco", "tabasco", "TAB"),
        ("Tamaulipas", "tamaulipas", "TAM"),
        ("Tlaxcala", "tlaxcala", "TLA"),
        ("Veracruz", "veracruz", "VER"),
        ("Yucatán", "yucatan", "YUC"),
        ("Zacatecas", "zacatecas", "ZAC"),
    ],
    "bz": [
        ("Belize District", "belize-district", "BZ"),
        ("Cayo", "cayo", "CY"),
        ("Corozal", "corozal", "CZL"),
        ("Orange Walk", "orange-walk", "OW"),
        ("Stann Creek", "stann-creek", "SC"),
        ("Toledo", "toledo", "TOL"),
    ],
    "gt": [
        ("Alta Verapaz", "alta-verapaz", "AV"),
        ("Baja Verapaz", "baja-verapaz", "BV"),
        ("Chimaltenango", "chimaltenango", "CM"),
        ("Chiquimula", "chiquimula", "CQ"),
        ("El Progreso", "el-progreso", "PR"),
        ("Escuintla", "escuintla", "ES"),
        ("Guatemala", "guatemala-department", "GU"),
        ("Huehuetenango", "huehuetenango", "HU"),
        ("Izabal", "izabal", "IZ"),
        ("Jalapa", "jalapa", "JA"),
        ("Jutiapa", "jutiapa", "JU"),
        ("Petén", "peten", "PE"),
        ("Quetzaltenango", "quetzaltenango", "QZ"),
        ("Quiché", "quiche", "QC"),
        ("Retalhuleu", "retalhuleu", "RE"),
        ("Sacatepéquez", "sacatepequez", "SA"),
        ("San Marcos", "san-marcos", "SM"),
        ("Santa Rosa", "santa-rosa", "SR"),
        ("Sololá", "solola", "SO"),
        ("Suchitepéquez", "suchitepequez", "SU"),
        ("Totonicapán", "totonicapan", "TO"),
        ("Zacapa", "zacapa", "ZA"),
    ],
    "sv": [
        ("Ahuachapán", "ahuachapan", "AH"),
        ("Cabañas", "cabanas", "CA"),
        ("Chalatenango", "chalatenango", "CH"),
        ("Cuscatlán", "cuscatlan", "CU"),
        ("La Libertad", "la-libertad", "LI"),
        ("La Paz", "la-paz", "PA"),
        ("La Unión", "la-union", "UN"),
        ("Morazán", "morazan", "MO"),
        ("San Miguel", "san-miguel", "SM"),
        ("San Salvador", "san-salvador", "SS"),
        ("San Vicente", "san-vicente", "SV"),
        ("Santa Ana", "santa-ana", "SA"),
        ("Sonsonate", "sonsonate", "SO"),
        ("Usulután", "usulutan", "US"),
    ],
    "hn": [
        ("Atlántida", "atlantida", "AT"),
        ("Choluteca", "choluteca", "CH"),
        ("Colón", "colon", "CL"),
        ("Comayagua", "comayagua", "CM"),
        ("Copán", "copan", "CP"),
        ("Cortés", "cortes", "CR"),
        ("El Paraíso", "el-paraiso", "EP"),
        ("Francisco Morazán", "francisco-morazan", "FM"),
        ("Gracias a Dios", "gracias-a-dios", "GD"),
        ("Intibucá", "intibuca", "IN"),
        ("Islas de la Bahía", "islas-de-la-bahia", "IB"),
        ("La Paz", "la-paz", "LP"),
        ("Lempira", "lempira", "LE"),
        ("Ocotepeque", "ocotepeque", "OC"),
        ("Olancho", "olancho", "OL"),
        ("Santa Bárbara", "santa-barbara", "SB"),
        ("Valle", "valle", "VA"),
        ("Yoro", "yoro", "YO"),
    ],
    "ni": [
        ("Boaco", "boaco", "BO"),
        ("Carazo", "carazo", "CA"),
        ("Chinandega", "chinandega", "CI"),
        ("Chontales", "chontales", "CO"),
        ("Estelí", "esteli", "ES"),
        ("Granada", "granada", "GR"),
        ("Jinotega", "jinotega", "JI"),
        ("León", "leon", "LE"),
        ("Madriz", "madriz", "MD"),
        ("Managua", "managua", "MN"),
        ("Masaya", "masaya", "MS"),
        ("Matagalpa", "matagalpa", "MT"),
        ("Nueva Segovia", "nueva-segovia", "NS"),
        ("Río San Juan", "rio-san-juan", "SJ"),
        ("Rivas", "rivas", "RI"),
        ("North Caribbean Coast Autonomous Region", "north-caribbean-coast", "AN"),
        ("South Caribbean Coast Autonomous Region", "south-caribbean-coast", "AS"),
    ],
    "cr": [
        ("Alajuela", "alajuela", "A"),
        ("Cartago", "cartago", "C"),
        ("Guanacaste", "guanacaste", "G"),
        ("Heredia", "heredia", "H"),
        ("Limón", "limon", "L"),
        ("Puntarenas", "puntarenas", "P"),
        ("San José", "san-jose", "SJ"),
    ],
    "pa": [
        ("Bocas del Toro", "bocas-del-toro", "1"),
        ("Coclé", "cocle", "2"),
        ("Colón", "colon", "3"),
        ("Chiriquí", "chiriqui", "4"),
        ("Darién", "darien", "5"),
        ("Herrera", "herrera", "6"),
        ("Los Santos", "los-santos", "7"),
        ("Panamá", "panama-province", "8"),
        ("Veraguas", "veraguas", "9"),
        ("West Panamá", "west-panama", "10"),
        ("Emberá-Wounaan", "embera-wounaan", "EM"),
        ("Guna Yala", "guna-yala", "KY"),
        ("Ngäbe-Buglé", "ngabe-bugle", "NB"),
    ],
    "gb": [
        ("England", "england", "ENG"),
        ("Scotland", "scotland", "SCT"),
        ("Wales", "wales", "WLS"),
        ("Northern Ireland", "northern-ireland", "NIR"),
    ],
    "au": [
        ("Australian Capital Territory", "australian-capital-territory", "ACT"),
        ("New South Wales", "new-south-wales", "NSW"),
        ("Northern Territory", "northern-territory", "NT"),
        ("Queensland", "queensland", "QLD"),
        ("South Australia", "south-australia", "SA"),
        ("Tasmania", "tasmania", "TAS"),
        ("Victoria", "victoria", "VIC"),
        ("Western Australia", "western-australia", "WA"),
    ],
}

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
        parser.add_argument(
            "--skip-us-fips",
            action="store_true",
            help="Skip US state/county FIPS import (still seeds countries + non-US admin1).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["skip_categories"]:
            self._seed_categories()
        if not options["skip_geo"]:
            self._seed_geo(skip_us_fips=options["skip_us_fips"])
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

    def _seed_geo(self, *, skip_us_fips: bool = False):
        if not skip_us_fips and not FIPS_CSV.is_file():
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

        if not skip_us_fips:
            self._seed_us_fips()

        self._seed_non_us_admin1()

        self.stdout.write(
            f"Geo: {GeographicArea.objects.filter(area_type='country').count()} countries, "
            f"{GeographicArea.objects.filter(area_type='admin1').count()} admin1, "
            f"{GeographicArea.objects.filter(area_type='admin2').count()} admin2"
        )

    def _seed_us_fips(self):
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

    def _seed_non_us_admin1(self):
        """Seed first administrative level for non-US starter countries."""
        for country_slug, areas in ADMIN1_BY_COUNTRY.items():
            country = GeographicArea.objects.filter(
                parent=None,
                slug=country_slug,
                area_type=GeographicArea.AreaType.COUNTRY,
            ).first()
            if not country:
                continue
            used_slugs = set(
                GeographicArea.objects.filter(
                    parent=country,
                    area_type=GeographicArea.AreaType.ADMIN1,
                ).values_list("slug", flat=True)
            )
            for sort_order, (name, slug, external_code) in enumerate(areas):
                existing = GeographicArea.objects.filter(
                    parent=country,
                    area_type=GeographicArea.AreaType.ADMIN1,
                    external_code=external_code,
                ).first()
                if existing:
                    existing.name = name
                    existing.slug = slug
                    existing.country_code = country.country_code
                    existing.is_active = True
                    existing.sort_order = sort_order
                    existing.save()
                    used_slugs.add(existing.slug)
                    continue

                by_slug = GeographicArea.objects.filter(
                    parent=country,
                    area_type=GeographicArea.AreaType.ADMIN1,
                    slug=slug,
                ).first()
                if by_slug:
                    by_slug.name = name
                    by_slug.external_code = external_code
                    by_slug.country_code = country.country_code
                    by_slug.is_active = True
                    by_slug.sort_order = sort_order
                    by_slug.save()
                    used_slugs.add(by_slug.slug)
                    continue

                unique = slug if slug not in used_slugs else _unique_slug(name, used_slugs)
                used_slugs.add(unique)
                GeographicArea.objects.create(
                    parent=country,
                    slug=unique,
                    name=name,
                    area_type=GeographicArea.AreaType.ADMIN1,
                    country_code=country.country_code,
                    external_code=external_code,
                    is_active=True,
                    sort_order=sort_order,
                )
