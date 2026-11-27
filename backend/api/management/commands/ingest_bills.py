from django.core.management.base import BaseCommand

from api.bill_analysis import analyze_bill, store_bill
from api.nc_bills import list_bills


class Command(BaseCommand):
    help = "Download North Carolina House and Senate bills and analyze them with local Ollama (qwen3.5:9b)."

    def add_arguments(self, parser):
        parser.add_argument("--session", type=int, default=2025)
        parser.add_argument(
            "--chambers",
            default="H,S",
            help="H for House, S for Senate.",
        )
        parser.add_argument("--limit", type=int, default=5, help="Bills per chamber.")
        parser.add_argument(
            "--skip-analysis",
            action="store_true",
            help="Store bills without calling Ollama.",
        )

    def handle(self, *args, **options):
        codes = [part.strip().upper() for part in options["chambers"].split(",") if part.strip()]
        for code in codes:
            if code not in {"H", "S"}:
                self.stderr.write(f"Unknown chamber {code}. Use H or S.")
                continue
            rows = list_bills(options["session"], code)[: options["limit"]]
            self.stdout.write(f"{code}: {len(rows)} bills")
            for row in rows:
                number = int(row["billNumber"])
                bill = store_bill(options["session"], code, number)
                self.stdout.write(f"  stored {bill}: {bill.title}")
                if options["skip_analysis"]:
                    continue
                analyze_bill(bill)
                if bill.analysis_status == "done":
                    self.stdout.write(self.style.SUCCESS(f"  analyzed {bill}"))
                else:
                    self.stderr.write(f"  analysis failed: {bill.analysis_error}")
