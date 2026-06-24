"""Contract cho `PurgeDocumentService` — hợp đồng nghiệp vụ enqueue purge.

Khai báo "cái gì" (hợp đồng); implementation ở `services/v1`. Việc đẩy task
Celery và trả `202 Accepted` là chi tiết của implementation, không lộ ở đây.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rest_framework.response import Response

    from ....http.requests.v1 import PurgeDocumentDTO


class PurgeDocumentServiceInterface(ABC):
    """Hợp đồng enqueue dọn OpenSearch/KG cho document đã gỡ khỏi kho."""

    @abstractmethod
    def purge(self, dto: PurgeDocumentDTO) -> Response:
        """Enqueue purge cho `dto.document_id` và trả `202 Accepted`."""
        ...
