"""Các class thao tác OpenSearch của module Chatbot — mỗi index một file.

- `indexer.py`         — `OpenSearchIndexer`: ghi parent-child (rag-index).
- `summary_indexer.py` — `SummaryIndexer`: ghi tóm tắt 1-doc-mỗi-tài-liệu.
- `retriever.py`       — `Retriever`: hybrid search (BM25 + kNN) + RRF.

Tất cả kế thừa `BaseOpenSearchClient` (modules.base.clients) — connection/env do
base lo. LTM của chat (`ChatHistoryIndex`) nằm ở `services/chat/ltm.py` vì gắn
với nghiệp vụ hội thoại, không phải RAG.
"""

from .indexer import OpenSearchIndexer
from .retriever import Retriever
from .summary_indexer import SummaryIndexer

__all__ = ["OpenSearchIndexer", "Retriever", "SummaryIndexer"]
