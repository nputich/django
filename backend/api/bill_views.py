from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import LegislativeBill


def bill_payload(bill: LegislativeBill) -> dict:
    return {
        "id": bill.id,
        "session_year": bill.session_year,
        "bill_type": bill.bill_type,
        "bill_number": bill.bill_number,
        "chamber": bill.chamber,
        "title": bill.title,
        "introduced_date": bill.introduced_date,
        "latest_action": bill.latest_action,
        "latest_action_date": bill.latest_action_date,
        "official_summary": bill.official_summary,
        "analysis_summary": bill.analysis_summary,
        "analysis": bill.analysis,
        "analysis_status": bill.analysis_status,
        "analysis_model": bill.analysis_model,
        "analyzed_at": bill.analyzed_at,
        "source_url": bill.source_url,
    }


class LegislativeBillListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = LegislativeBill.objects.all()
        chamber = request.query_params.get("chamber")
        if chamber in {"house", "senate"}:
            qs = qs.filter(chamber=chamber)
        bills = qs[:100]
        return Response([bill_payload(bill) for bill in bills])


class LegislativeBillDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        bill = LegislativeBill.objects.filter(pk=pk).first()
        if bill is None:
            return Response({"detail": "Not found."}, status=404)
        payload = bill_payload(bill)
        payload["bill_text"] = bill.bill_text
        return Response(payload)
