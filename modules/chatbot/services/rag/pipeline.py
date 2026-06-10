"""Orchestrator pipeline RAG: chatbot_document → text → chunk → embed → index.

Đây là phần thân thật của task `chatbot.ingest_document` (Phase 1). Đọc tài liệu
từ DB dùng chung (managed=False, chỉ ghi DATA cột `status`), tải file gốc từ S3,
trích text bằng Gemini, chunk + embed, rồi index parent-child vào OpenSearch.

Mọi lỗi đều đánh document FAILED và `logger.exception` — không để task chết âm
thầm, đồng thời không raise lại để tránh worker retry vô hạn ở Phase 1.
"""

from __future__ import annotations

import logging

from .chunker import chunk_text
from .config import ChunkConfig, GeminiConfig, OpenSearchConfig, S3Config
from .embedder import embed_chunks
from .exceptions import UnsupportedDocumentError
from .extractor import KIND_OTHER, detect_kind, extract_text
from .opensearch_indexer import OpenSearchIndexer
from .s3_reader import S3Reader

logger = logging.getLogger(__name__)


def _set_status(document_id: int, status: str) -> None:
    """Ghi `chatbot_documents.status` (DML trên bảng dùng chung, managed=False).

    `status` là value của `DocumentStatus` (TextChoices = str), truyền từ caller.
    """
    from modules.chatbot.models import ChatbotDocument  # lazy: cần Django app registry

    updated = ChatbotDocument.objects.filter(pk=document_id).update(status=status)
    if not updated:
        logger.warning("[pipeline] document_id=%s không tồn tại khi set %s", document_id, status)


def run_ingest_pipeline(document_id: int) -> None:
    """Chạy toàn bộ pipeline ingest cho 1 chatbot_documents.id."""
    from modules.chatbot.enums import DocumentStatus
    from modules.chatbot.models import ChatbotDocument

    logger.info("[pipeline] bắt đầu ingest document_id=%s", document_id)

    try:
        document = (
            ChatbotDocument.objects.select_related("media")
            .filter(pk=document_id)
            .first()
        )
        if document is None:
            logger.warning("[pipeline] document_id=%s không tồn tại, bỏ qua", document_id)
            return

        # Đánh dấu đang xử lý ngay khi nhận tài liệu hợp lệ.
        _set_status(document_id, DocumentStatus.PENDING)

        media = document.media
        kind = detect_kind(media.mime_type, media.file_type)

        # Gate loại file: chỉ PDF/Word đi tiếp; còn lại FAILED + return.
        if kind == KIND_OTHER:
            logger.warning(
                "[pipeline] document_id=%s loại không hỗ trợ (mime=%s file_type=%s) -> FAILED",
                document_id,
                media.mime_type,
                media.file_type,
            )
            _set_status(document_id, DocumentStatus.FAILED)
            return

        # Cấu hình từ env (tách theo nhóm).
        s3_config = S3Config.from_env()
        gemini_config = GeminiConfig.from_env()
        chunk_config = ChunkConfig.from_env()
        opensearch_config = OpenSearchConfig.from_env()

        # 1) Tải file gốc từ S3.
        file_bytes = S3Reader(s3_config).read_bytes(media.file_name)

        # 2) Trích text (PDF qua Gemini; Word -> UnsupportedDocumentError ở Phase 1).
        text = extract_text(file_bytes, kind, media.mime_type, gemini_config)
        if not text.strip():
            logger.warning("[pipeline] document_id=%s trích ra text rỗng -> FAILED", document_id)
            _set_status(document_id, DocumentStatus.FAILED)
            return

        # 3) Chunk + 4) embed.
        chunks = chunk_text(text, media.original_name, chunk_config)
        embedded = embed_chunks(chunks, opensearch_config.vector_dims, gemini_config)
        if not embedded:
            logger.warning(
                "[pipeline] document_id=%s không có chunk embed hợp lệ -> FAILED", document_id
            )
            _set_status(document_id, DocumentStatus.FAILED)
            return

        # 5) Index parent-child vào OpenSearch (idempotent).
        parent_meta = {
            "document_id": document_id,
            "media_id": media.pk,
            "original_name": media.original_name,
            "mime_type": media.mime_type,
            "file_type": media.file_type,
        }
        indexed = OpenSearchIndexer(opensearch_config).index_document(parent_meta, embedded)

        # 6) Thành công.
        _set_status(document_id, DocumentStatus.READY)
        logger.info(
            "[pipeline] document_id=%s READY (%d chunk đã index)", document_id, indexed
        )

    except UnsupportedDocumentError as exc:
        logger.warning("[pipeline] document_id=%s không hỗ trợ: %s -> FAILED", document_id, exc)
        _set_status(document_id, DocumentStatus.FAILED)
    except Exception:
        logger.exception("[pipeline] document_id=%s lỗi pipeline -> FAILED", document_id)
        _set_status(document_id, DocumentStatus.FAILED)
