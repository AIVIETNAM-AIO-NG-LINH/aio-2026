from rest_framework.routers import DefaultRouter

from .views import ExampleViewSet

router = DefaultRouter()
# /api/examples/ và /api/examples/{id}/
router.register(r"examples", ExampleViewSet, basename="example")

urlpatterns = router.urls
