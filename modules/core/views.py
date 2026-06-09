from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request):
    """Liveness/readiness probe: reports app status and database connectivity."""
    database_ok = True
    try:
        connection.ensure_connection()
    except Exception:  # pragma: no cover - exercised only when the DB is down
        database_ok = False

    payload = {
        "status": "ok" if database_ok else "degraded",
        "database": "up" if database_ok else "down",
    }
    return Response(payload, status=200 if database_ok else 503)
