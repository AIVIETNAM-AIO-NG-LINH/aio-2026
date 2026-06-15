"""Orchestrator pipeline RAG: chatbot_document → text → chunk → embed → index.

Đây là phần thân thật của task `chatbot.ingest_document` (Phase 1) — chạy trong
worker nền nên nằm ở `pipelines/`, không phải `services/` (vốn dành cho class
nhận request). Các helper hạ tầng của ingest (extract_helper, page_chunker,
config) nằm ở `support/`; bước dùng chung với retrieve (embedder, indexer…) vẫn
ở `services/`. Đọc tài liệu từ DB dùng chung (managed=False, chỉ ghi DATA cột
`status`), tải file gốc từ S3, trích text bằng Gemini, chunk + embed, rồi index
parent-child vào OpenSearch.

Lỗi chỉ bắt theo KIỂU của bên thứ 3 (`_EXTERNAL_ERRORS`: botocore/Gemini/
OpenSearch, cộng `UnsupportedDocumentError` chủ đích) trong MỘT try quanh các
bước gọi ra ngoài → FAILED, traceback trong log chỉ rõ bước hỏng. Lỗi code nội
bộ không khớp kiểu nào nên propagate lên vỏ task (`tasks/ingest.py` giữ lưới
an toàn cuối: log traceback + FAILED) — bug lộ nguyên hình, không bị nuốt.
"""

from __future__ import annotations

import logging

from botocore.exceptions import BotoCoreError, ClientError
from google.genai import errors as genai_errors
from opensearchpy.exceptions import OpenSearchException

from modules.base.clients.s3_client import S3Client

from ..rag.embedder import embed_chunks
from ..rag.exceptions import UnsupportedDocumentError
from ..lightrag.lightrag_client import LightRagIndexer
from ..opensearch import OpenSearchIndexer, SummaryIndexer
from ..support.extract_helper import extract_pages, pages_to_text
from ..support.page_chunker import PageChunk, chunk_pages

logger = logging.getLogger(__name__)

#: Kiểu lỗi của dịch vụ ngoài (S3/Gemini/OpenSearch) — pipeline CHỈ bắt những kiểu
#: này để đánh FAILED; lỗi code nội bộ propagate lên vỏ task (lưới an toàn cuối).
#: Lỗi mạng SDK chưa gói (httpx/urllib3…) cũng rơi xuống lưới task — vẫn FAILED.
_EXTERNAL_ERRORS = (BotoCoreError, ClientError, genai_errors.APIError, OpenSearchException)


def _set_status(document_id: int, status: str) -> None:
    """Ghi `chatbot_documents.status` qua repository (bảng dùng chung, managed=False).

    `status` là value của `DocumentStatus` (TextChoices = str), truyền từ caller.
    """
    from modules.chatbot.app.repositories import ChatbotDocumentRepository  # lazy: cần Django app registry

    if not ChatbotDocumentRepository().set_status(document_id, status):
        logger.warning("[pipeline] document_id=%s không tồn tại khi set %s", document_id, status)


def _index_summary_safe(document_id: int, media_id: int, text: str) -> None:
    """Index summary (Phase 2) — nuốt mọi lỗi để không ảnh hưởng status READY."""
    try:
        SummaryIndexer().index_summary(document_id, media_id, text)
    except Exception:
        logger.exception(
            "[pipeline] document_id=%s lỗi index summary (bỏ qua, vẫn READY)", document_id
        )


def _index_lightrag_safe(document_id: int, text: str) -> None:
    """Index LightRAG/KG (Phase 2) — fail-safe, tự bỏ qua nếu LIGHTRAG_ENABLED=false."""
    try:
        LightRagIndexer().index_document(document_id, text)
    except Exception:
        logger.exception(
            "[pipeline] document_id=%s lỗi index LightRAG (bỏ qua, vẫn READY)", document_id
        )


def _attach_pages(
    chunks: list[PageChunk],
    embedded: list[tuple[str, list[float]]],
) -> list[tuple[str, list[float], int | None]]:
    """Gắn lại số trang cho từng (text, vector) sau bước embed.

    `embed_chunks` giữ NGUYÊN thứ tự và chỉ loại bớt chunk sai số chiều, nên kết
    quả là một dãy con (subsequence) đúng thứ tự của `chunks`. Quét tịnh tiến để
    khớp text → trang; chịu được cả khi text trùng nhau giữa các trang.
    """
    children: list[tuple[str, list[float], int | None]] = []
    cursor = 0
    total = len(chunks)
    for text, vector in embedded:
        while cursor < total and chunks[cursor].text != text:
            cursor += 1
        page = chunks[cursor].page if cursor < total else None
        children.append((text, vector, page))
        cursor += 1
    return children


def run_ingest_pipeline(document_id: int) -> None:
    """Chạy toàn bộ pipeline ingest cho 1 chatbot_documents.id."""
    from modules.chatbot.app.enums import DocumentStatus
    from modules.chatbot.app.repositories import ChatbotDocumentRepository

    logger.info("[pipeline] bắt đầu ingest document_id=%s", document_id)

    document = ChatbotDocumentRepository().find_with_media(document_id)
    if document is None:
        logger.warning("[pipeline] document_id=%s không tồn tại, bỏ qua", document_id)
        return

    # Đánh dấu đang xử lý ngay khi nhận tài liệu hợp lệ.
    _set_status(document_id, DocumentStatus.PENDING)

    media = document.media
    # Không có media (media_id null hoặc bản ghi mồ côi) → không thể đọc file → FAILED.
    if media is None:
        logger.warning("[pipeline] document_id=%s thiếu media -> FAILED", document_id)
        _set_status(document_id, DocumentStatus.FAILED)
        return

    kind = media.document_kind

    # Gate loại file: chỉ PDF/Word đi tiếp; còn lại FAILED + return.
    if kind is None:
        logger.warning(
            "[pipeline] document_id=%s loại không hỗ trợ (mime=%s file_type=%s) -> FAILED",
            document_id,
            media.mime_type,
            media.file_type,
        )
        _set_status(document_id, DocumentStatus.FAILED)
        return

    # S3/Gemini/OpenSearch do client ở base tự quản; config chunk + header
    # do page_chunker tự đọc từ env.
    indexer = OpenSearchIndexer()

    # Các bước 1-5 gọi dịch vụ ngoài nằm chung MỘT try, nhưng CHỈ bắt kiểu lỗi
    # của bên thứ 3 (`_EXTERNAL_ERRORS`) — lỗi code nội bộ (chunk, gắn trang…)
    # không khớp kiểu nên propagate lên vỏ task, lộ nguyên traceback.
    try:
        # 1) Tải file gốc từ S3 (S3Client ở base tự đọc env AWS_S3_*).
        file_bytes = S3Client().read_bytes(media.file_name)

        # 2) Trích text THEO TRANG (PDF/Word qua extractor lai pypdf + Gemini OCR).
        pages = extract_pages(file_bytes, kind, media.mime_type)
        text = pages_to_text(pages)  # full-text cho summary/LightRAG
        if not text.strip():
            logger.warning("[pipeline] document_id=%s trích ra text rỗng -> FAILED", document_id)
            _set_status(document_id, DocumentStatus.FAILED)
            return

        # 3) Chunk THEO TRANG (mỗi chunk mang số trang + contextual header) +
        #    4) embed text từng chunk. Header (kèm `kind`) đã nằm trong chunk.text
        #    nên vừa vào vector lúc embed, vừa lưu nguyên trong chunk_text ở index.
        chunks = chunk_pages(pages, media.original_name, kind=kind)
        embedded = embed_chunks(
            [chunk.text for chunk in chunks], indexer.vector_dims
        )
        if not embedded:
            logger.warning(
                "[pipeline] document_id=%s không có chunk embed hợp lệ -> FAILED", document_id
            )
            _set_status(document_id, DocumentStatus.FAILED)
            return

        # Gắn lại số trang cho từng vector trước khi index.
        children = _attach_pages(chunks, embedded)

        # 5) Index parent-child vào OpenSearch (idempotent), child kèm field `page`.
        parent_meta = {
            "document_id": document_id,
            "media_id": media.pk,
            "original_name": media.original_name,
            "mime_type": media.mime_type,
            "file_type": media.file_type,
            "page_count": len(pages),
        }
        indexed = indexer.index_document(parent_meta, children)
    except UnsupportedDocumentError as exc:
        logger.warning("[pipeline] document_id=%s không hỗ trợ: %s -> FAILED", document_id, exc)
        _set_status(document_id, DocumentStatus.FAILED)
        return
    except _EXTERNAL_ERRORS:
        logger.exception(
            "[pipeline] document_id=%s lỗi dịch vụ ngoài (S3/Gemini/OpenSearch) -> FAILED",
            document_id,
        )
        _set_status(document_id, DocumentStatus.FAILED)
        return

    # 6) Phần phụ Phase 2 — fail-safe: lỗi KHÔNG đổi status sang FAILED, chỉ log.
    #    Chạy sau khi rag-index chính đã xong (tài liệu coi như thành công).
    _index_summary_safe(document_id, media.pk, text)
    _index_lightrag_safe(document_id, text)

    # 7) Thành công (phần chính đã index xong → READY bất kể summary/KG).
    _set_status(document_id, DocumentStatus.READY)
    logger.info(
        "[pipeline] document_id=%s READY (%d chunk đã index)", document_id, indexed
    )
