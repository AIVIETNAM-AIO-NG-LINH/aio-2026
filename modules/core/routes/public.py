"""Routes công khai của module Core.

Nối vào config/urls.py dưới prefix `api/`, nên path đầy đủ là `GET /api/health/`.
"""

from django.urls import path

from ..app.http.controllers import HealthController

urlpatterns = [
    path("health/", HealthController.as_view(), name="health"),
]
