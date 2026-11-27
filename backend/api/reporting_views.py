"""Organization reporting endpoint (questions × tags × months)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .meeting_export import csv_http_response, render_csv
from .models import Organization
from .org_access import get_admin_organization
from .reporting_service import REPORT_CSV_COLUMNS, build_report, parse_filters, report_csv_rows


class OrganizationReportView(APIView):
    """
    GET ?from=YYYY-MM-DD&to=YYYY-MM-DD&tags=1,2&q=text&source=all|meetings|surveys
        [&export=csv]   (``format`` is reserved by DRF)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            organization = get_admin_organization(request.user, slug)
        except Organization.DoesNotExist:
            return Response(
                {"detail": "Organization not found or you are not an admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
        filters = parse_filters(request.query_params)
        report = build_report(organization, filters)
        if (request.query_params.get("export") or "").lower() == "csv":
            name = f"{organization.slug}-report-{report['filters']['from']}-to-{report['filters']['to']}.csv"
            return csv_http_response(name, render_csv(report_csv_rows(report), REPORT_CSV_COLUMNS))
        return Response(report)
