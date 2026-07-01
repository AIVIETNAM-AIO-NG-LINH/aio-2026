"""ChatbotCatalog — catalog chuỗi UI của module Chatbot (mirror quy ước
`Modules\\*\\Catalog` bên Laravel: mỗi module/feature có ĐÚNG 1 catalog).

Namespace khai báo 1 lần (hằng `_NS`), mỗi key (`name`) khai báo 1 lần ở đây;
call-site gọi qua hằng: `translate("Hội thoại không tồn tại", ChatbotCatalog.CONVERSATION_NOT_FOUND)`.
Chuỗi dùng chung nhiều module để ở `modules.base.app.catalogs.CommonCatalog`.
"""

from __future__ import annotations

from modules.base.app.catalogs import LangCatalog


class ChatbotCatalog(LangCatalog):
    """Key chuỗi UI của feature Chatbot — giá trị IN HOA để dễ đọc trong DB."""

    _NS = "CHATBOT"

    # Luồng chat (ChatService)
    CONVERSATION_PROCESSING = _NS + ".CONVERSATION_PROCESSING"
    CONVERSATION_NOT_FOUND = _NS + ".CONVERSATION_NOT_FOUND"
    ANSWER_GENERATION_FAILED = _NS + ".ANSWER_GENERATION_FAILED"
    TOKEN_QUOTA_EXCEEDED = _NS + ".TOKEN_QUOTA_EXCEEDED"
    TOKEN_QUOTA_UNAVAILABLE = _NS + ".TOKEN_QUOTA_UNAVAILABLE"

    # Validate chat (ChatRequest)
    QUESTION_REQUIRED = _NS + ".QUESTION_REQUIRED"
    QUESTION_BLANK = _NS + ".QUESTION_BLANK"
    CONVERSATION_ID_INVALID = _NS + ".CONVERSATION_ID_INVALID"
    CONVERSATION_ID_MIN = _NS + ".CONVERSATION_ID_MIN"
    MEDIA_IDS_INVALID = _NS + ".MEDIA_IDS_INVALID"
    MEDIA_ID_INVALID = _NS + ".MEDIA_ID_INVALID"

    # Validate ingest nội bộ (IngestDocumentRequest)
    DOCUMENT_ID_REQUIRED = _NS + ".DOCUMENT_ID_REQUIRED"
    DOCUMENT_ID_INVALID = _NS + ".DOCUMENT_ID_INVALID"
    DOCUMENT_ID_MIN = _NS + ".DOCUMENT_ID_MIN"
    DOCUMENT_NOT_FOUND = _NS + ".DOCUMENT_NOT_FOUND"

    # Validate đổi tên hội thoại (UpdateConversationRequest)
    TITLE_REQUIRED = _NS + ".TITLE_REQUIRED"
    TITLE_BLANK = _NS + ".TITLE_BLANK"
    TITLE_MAX = _NS + ".TITLE_MAX"

    # Kết quả thao tác hội thoại (ChatService)
    RENAME_SUCCESS = _NS + ".RENAME_SUCCESS"
    DELETE_SUCCESS = _NS + ".DELETE_SUCCESS"
