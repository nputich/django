import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.bill_analysis import analyze_bill
from api.models import LegislativeBill


class BillAnalysisTests(TestCase):
    def test_local_ollama_analysis_is_stored(self):
        bill = LegislativeBill.objects.create(
            session_year=2025,
            bill_type="hr",
            bill_number=1,
            chamber="house",
            title="Example roads bill",
            official_summary="This bill funds bridge repair.",
        )
        payload = {
            "message": {
                "content": json.dumps(
                    {
                        "summary": "Funds bridge repair.",
                        "what_it_does": ["Pays for bridges"],
                        "who_is_affected": ["Drivers"],
                        "key_provisions": ["Grant program"],
                        "open_questions": [],
                    }
                )
            }
        }
        with patch("api.bill_analysis._http_post_json", return_value=payload):
            analyze_bill(bill)
        bill.refresh_from_db()
        self.assertEqual(bill.analysis_status, "done")
        self.assertEqual(bill.analysis_model, "qwen3.5:9b")
        self.assertIn("bridge", bill.analysis_summary.lower())

    def test_authenticated_list(self):
        LegislativeBill.objects.create(
            session_year=2025,
            bill_type="s",
            bill_number=2,
            chamber="senate",
            title="Senate example",
            analysis_status="done",
            analysis_summary="A senate bill.",
        )
        user = User.objects.create_user("bills", password="Pass1234!")
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/api/bills/?chamber=senate")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["bill_type"], "s")
