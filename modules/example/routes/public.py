"""Routes công khai của module Example.

Nối vào config/urls.py dưới prefix `api/`, nên path đầy đủ là
`/api/examples/` và `/api/examples/{id}/` (CRUD qua DefaultRouter).
"""

from rest_framework.routers import DefaultRouter

from ..app.http.controllers import ExampleController

router = DefaultRouter()
router.register(r"examples", ExampleController, basename="example")

urlpatterns = router.urls
