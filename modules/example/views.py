from rest_framework import viewsets

from .models import Example
from .serializers import ExampleSerializer


class ExampleViewSet(viewsets.ModelViewSet):
    """CRUD đầy đủ: list / create / retrieve / update / partial_update / destroy."""

    queryset = Example.objects.all()
    serializer_class = ExampleSerializer
