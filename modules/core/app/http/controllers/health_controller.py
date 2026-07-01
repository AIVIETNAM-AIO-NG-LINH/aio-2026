"""Controller health-check (`GET /api/health/`) — liveness/readiness probe."""

from __future__ import annotations

from django.db import connection
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthController(APIView):
    """GET `/api/health/` — báo trạng thái app + kết nối database."""

    def get(self, request: Request, *args, **kwargs) -> Response:
        database_ok = True
        try:
            connection.ensure_connection()
        except Exception:  # pragma: no cover - chỉ chạy khi DB down
            database_ok = False

        payload = {
            "status": "ok" if database_ok else "degraded",
            "database": "up" if database_ok else "down",
        }
        return Response(payload, status=200 if database_ok else 503)
