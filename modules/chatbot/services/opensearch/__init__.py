"""Các class thao tác OpenSearch của module Chatbot — mỗi index một file.

- `indexer.py`         — `OpenSearchIndexer`: ghi parent-child (rag-index).
- `summary_indexer.py` — `SummaryIndexer`: ghi tóm tắt 1-doc-mỗi-tài-liệu.
- `retriever.py`       — `Retriever`: hybrid search (BM25 + kNN) + RRF.
- `ltm.py`             — `ChatHistoryIndex`: LTM hội thoại (index + kNN theo user).

Tất cả kế thừa `BaseOpenSearchClient` (modules.base.clients) — connection/env do
base lo.
"""

from .indexer import OpenSearchIndexer
from .ltm import ChatHistoryIndex
from .retriever import Retriever
from .summary_indexer import SummaryIndexer

__all__ = ["ChatHistoryIndex", "OpenSearchIndexer", "Retriever", "SummaryIndexer"]
