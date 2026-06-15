"""Contract cho `IngestDocumentService` — hợp đồng nghiệp vụ enqueue ingest.

Khai báo "cái gì" (hợp đồng); implementation ở `services/v1`. Việc đẩy task
Celery và trả `202 Accepted` là chi tiết của implementation, không lộ ở đây.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rest_framework.response import Response

    from ....http.requests.v1 import IngestDocumentDTO


class IngestDocumentServiceInterface(ABC):
    """Hợp đồng enqueue pipeline ingest cho document đã validate."""

    @abstractmethod
    def ingest(self, dto: IngestDocumentDTO) -> Response:
        """Enqueue ingest cho `dto.document_id` và trả `202 Accepted`."""
        ...
