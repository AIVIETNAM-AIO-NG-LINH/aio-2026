"""Đính kèm file người dùng vào lượt chat bằng Gemini Files API (native multimodal).

Luồng (bám cách ga-ai, điều chỉnh cho ai-aio):
  FE gửi `media_ids` (bản ghi `media` ĐÃ có sẵn, do api-aio sở hữu) → với mỗi media:
  tải bytes từ **S3** → Word convert sang PDF (LibreOffice) → **ĐẨY lên Gemini Files
  API** → lấy URI → `types.Part.from_uri` để Gemini **ĐỌC FILE TRỰC TIẾP** (không
  extract text, không index RAG).

KHÔNG ĐỘNG VÀO BẢNG `media`: URI + trạng thái đã-đẩy + TTL cache hoàn toàn ở bảng
`chatbot_message_files` (ai-aio sở hữu). Bảng `media` chỉ được ĐỌC (file_name để tải
S3, mime_type, original_name, document_kind).

Scoped theo hội thoại: mỗi file gắn vào đúng `ChatMessage` (role user) của lượt gửi;
các lượt sau nạp lại qua lịch sử (`history_parts`) — chỉ đúng hội thoại đó mới thấy.

Mọi bước FAIL-SAFE theo TỪNG file: lỗi 1 file (media mất, S3 lỗi, convert/Gemini lỗi)
chỉ bỏ file đó + log, KHÔNG làm hỏng cả lượt chat.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone
from google.genai import types

from ..chat_pipeline.config import ChatConfig

if TYPE_CHECKING:
    from ..models import ChatConversation, ChatMessage, ChatMessageFile
    from modules.media.app.models import Media

logger = logging.getLogger(__name__)

#: Mime PDF — đích sau khi convert Word, cũng là loại Gemini đọc trực tiếp.
_PDF_MIME = "application/pdf"


class ChatAttachments:
    """Đẩy media lên Gemini + dựng `types.Part` cho lượt hiện tại và cho lịch sử."""

    def __init__(self) -> None:
        self._config = ChatConfig.from_env()
        # Lazy import repo để tránh phụ thuộc vòng lúc nạp module.
        from modules.media.app.repositories import MediaRepository

        from ..repositories import ChatMessageFileRepository

        self._files = ChatMessageFileRepository()
        self._media = MediaRepository()

    # --- Lượt hiện tại -----------------------------------------------------
    def attach_to_turn(
        self,
        conversation: ChatConversation,
        message: ChatMessage,
        media_ids: tuple[int, ...],
    ) -> tuple[list[types.Part], list[str]]:
        """Đẩy `media_ids` lên Gemini + lưu row + trả `(parts, tên_file)` cho lượt này.

        Bỏ trùng (giữ thứ tự), cắt theo trần `attached_files_max`. Mỗi media fail-safe:
        lỗi → bỏ file đó. `parts` để gắn vào `Content`, `tên_file` để nhắc model trong
        prompt + cho trích nguồn. Tắt qua env `CHAT_ATTACHED_FILES_ENABLED=false`.
        """
        if not media_ids or not self._config.attached_files_enabled:
            return [], []

        unique_ids = list(dict.fromkeys(int(m) for m in media_ids))
        unique_ids = unique_ids[: self._config.attached_files_max]

        medias = self._load_medias(unique_ids)

        parts: list[types.Part] = []
        names: list[str] = []
        for media_id in unique_ids:
            media = medias.get(media_id)
            if media is None:
                logger.warning("[attach] media_id=%s không tồn tại, bỏ qua", media_id)
                continue
            part = self._attach_one(conversation, message, media)
            if part is not None:
                parts.append(part)
                names.append(media.original_name or f"media#{media_id}")
        return parts, names

    def _attach_one(
        self,
        conversation: ChatConversation,
        message: ChatMessage,
        media: Media,
    ) -> types.Part | None:
        """Lo 1 media: lấy/đẩy URI Gemini → lưu row đính kèm → trả Part (None nếu lỗi)."""
        try:
            uri = self._resolve_uri(media)
        except Exception:
            logger.exception("[attach] media_id=%s đẩy Gemini lỗi, bỏ qua", media.pk)
            return None
        if not uri:
            return None

        # Lưu row đính kèm: vừa là cache URI, vừa link scope hội thoại, vừa cho history.
        self._files.create(
            {
                "conversation": conversation,
                "message": message,
                "media_id": media.pk,
                "gemini_uri": uri,
                "pushed_at": timezone.now(),
            }
        )
        return types.Part.from_uri(file_uri=uri, mime_type=_PDF_MIME)

    # --- Lịch sử -----------------------------------------------------------
    def history_parts(
        self, messages: list[ChatMessage]
    ) -> dict[int, list[types.Part]]:
        """Map `message_id` → list Part cho các message cũ CÓ đính kèm (re-push nếu hết hạn).

        Để các lượt hỏi tiếp vẫn "thấy" file đã đính kèm trước đó trong cùng hội thoại
        (giống `memory.py` của ga-ai). Fail-safe từng file.
        """
        if not messages or not self._config.attached_files_enabled:
            return {}

        rows_by_msg = self._files.for_message_ids([m.id for m in messages])
        if not rows_by_msg:
            return {}

        result: dict[int, list[types.Part]] = {}
        for msg_id, rows in rows_by_msg.items():
            parts = [p for p in (self._history_part(row) for row in rows) if p is not None]
            if parts:
                result[msg_id] = parts
        return result

    def _history_part(self, row: ChatMessageFile) -> types.Part | None:
        """Part cho 1 row lịch sử: dùng URI cache nếu còn hạn, hết hạn thì re-push.

        Mime đẩy Gemini luôn là PDF nên cache URI tự đủ dựng Part — KHÔNG cần load
        media khi còn hạn (chỉ load lại khi phải re-push).
        """
        if row.gemini_uri and self._is_fresh(row.pushed_at):
            return types.Part.from_uri(file_uri=row.gemini_uri, mime_type=_PDF_MIME)

        # Hết hạn / chưa có URI → re-push từ media gốc (media không còn thì bỏ qua file).
        media = self._load_medias([row.media_id]).get(row.media_id)
        if media is None:
            return None
        try:
            uri = self._push_media(media)
        except Exception:
            logger.exception("[attach] re-push media_id=%s (history) lỗi, bỏ qua", row.media_id)
            return None
        if not uri:
            return None

        # Cập nhật cache lên chính row lịch sử (lần sau khỏi re-push).
        row.gemini_uri = uri
        row.pushed_at = timezone.now()
        row.save(update_fields=["gemini_uri", "pushed_at", "updated_at"])
        return types.Part.from_uri(file_uri=uri, mime_type=_PDF_MIME)

    # --- Hạ tầng -----------------------------------------------------------
    def _resolve_uri(self, media: Media) -> str:
        """URI Gemini cho 1 media: tái dùng bản còn hạn nếu có, không thì đẩy mới."""
        cached = self._files.find_fresh_for_media(
            media.pk, self._config.gemini_file_ttl_hours
        )
        if cached and cached.gemini_uri:
            return cached.gemini_uri
        return self._push_media(media)

    @staticmethod
    def _push_media(media: Media) -> str:
        """Tải media từ S3 → (Word→PDF) → đẩy Gemini Files API → trả URI.

        Trả "" nếu loại file không hỗ trợ (chỉ PDF/Word). Lỗi S3/convert/Gemini
        propagate cho caller bắt (fail-safe ở `_attach_one`/`_history_part`). Mime đẩy
        lên Gemini luôn là PDF (PDF giữ nguyên, Word đã convert) nên không trả mime.
        """
        from modules.base.app.clients.gemini_client import GeminiClient
        from modules.base.app.clients.s3_client import S3Client

        kind = media.document_kind  # "PDF" / "WORD" / None
        if kind is None:
            return ""

        file_bytes = S3Client().read_bytes(media.file_name)
        mime = media.mime_type or _PDF_MIME
        # Lazy import KIND_WORD ở đây (không ở top) để hot-path chat khỏi kéo theo cả
        # stack extract_helper→pypdf khi không thực sự phải đẩy file.
        from .extract_helper import KIND_WORD

        if kind == KIND_WORD:
            # Gemini không đọc .doc/.docx trực tiếp → convert sang PDF trước (LibreOffice).
            from .word_to_pdf_helper import word_to_pdf

            file_bytes = word_to_pdf(file_bytes, media.mime_type)
            mime = _PDF_MIME

        uri, _ = GeminiClient().upload_file(file_bytes, mime)
        return uri

    def _is_fresh(self, pushed_at) -> bool:
        """`pushed_at` còn trong hạn TTL (Gemini Files API ~48h) hay không."""
        if pushed_at is None:
            return False
        return (timezone.now() - pushed_at) < timedelta(
            hours=self._config.gemini_file_ttl_hours
        )

    def _load_medias(self, media_ids: list[int]) -> dict[int, Media]:
        """Load `Media` theo list id qua repository, trả map id→media (đã loại soft-delete)."""
        return self._media.map_by_id(media_ids)
