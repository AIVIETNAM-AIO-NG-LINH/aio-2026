"""Client Google GenAI (Gemini) dùng chung ở base.

Một class tự quản trọn vòng đời như `S3Client`: đọc cấu hình từ env (12-factor),
khởi tạo `genai.Client`, expose thao tác sinh text + embedding (sync và async).
Bên ngoài KHÔNG tự dựng config hay genai client — chỉ gọi method:

    from modules.base.app.clients.gemini_client import GeminiClient
    gemini = GeminiClient()
    text = gemini.generate_text([prompt], model=gemini.summary_model)
    vectors = gemini.embed(texts, dims=768, task_type="RETRIEVAL_DOCUMENT")

Tên model đọc từ env, expose làm attribute public (`embedding_model`,
`extract_model`, `summary_model`) cho caller cần chọn model theo tác vụ.
`google-genai` import lazy bên trong class để module này an toàn với image slim
(web không cài deps RAG) — chỉ worker thực sự dùng mới cần SDK.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google import genai


def _env(name: str, default: str = "") -> str:
    """Đọc env, strip khoảng trắng; rỗng/không set → default."""
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


class GeminiClient:
    """Client mỏng quanh `genai.Client` — cấu hình qua env `GEMINI_*`/`EMBEDDING_MODEL`."""

    def __init__(self) -> None:
        self._api_key = _env("GEMINI_API_KEY")
        # gemini-embedding-001 ở 768 chiều (MRL); caller tự L2-normalize sau embed.
        self.embedding_model = _env("EMBEDDING_MODEL", default="gemini-embedding-001")
        # Model multimodal đọc PDF → text. Override qua env nếu Google đổi tên.
        self.extract_model = _env("GEMINI_EXTRACT_MODEL", default="gemini-2.5-flash")
        # Model Flash sinh tóm tắt (summary index) + trích entity (LightRAG).
        self.summary_model = _env("GEMINI_SUMMARY_MODEL", default="gemini-2.5-flash")
        self._client = self._build_client()

    def _build_client(self) -> "genai.Client":
        """Tạo `genai.Client` từ `GEMINI_API_KEY`.

        Raise ValueError sớm nếu thiếu API key — rõ ràng hơn để lỗi xảy ra sâu
        trong SDK lúc gọi model.
        """
        from google import genai  # lazy import: image slim (web) không cài google-genai

        if not self._api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình")
        return genai.Client(api_key=self._api_key)

    # --- Sinh text -----------------------------------------------------------
    def generate_text(self, contents: list[Any], model: str) -> str:
        """Gọi non-stream, trả text đã strip ("" nếu model không trả text).

        `contents` theo chuẩn google-genai: list str hoặc `types.Part` (multimodal).
        """
        response = self._client.models.generate_content(model=model, contents=contents)
        return (response.text or "").strip()

    async def agenerate_text(self, contents: list[Any], model: str) -> str:
        """Bản async của `generate_text` (cho LightRAG llm_model_func)."""
        response = await self._client.aio.models.generate_content(
            model=model, contents=contents
        )
        return (response.text or "").strip()

    # --- Sinh JSON có cấu trúc (structured output) ---------------------------
    def generate_json(
        self, contents: list[Any], model: str, response_schema: Any
    ) -> tuple[str, Any]:
        """Gọi non-stream ở chế độ JSON (response_schema), trả `(json_text, usage)`.

        Bật `response_mime_type="application/json"` + `response_schema` để model BẮT
        BUỘC trả JSON đúng khuôn (dùng cho sơ đồ tư duy). Trả text JSON THÔ (caller tự
        `json.loads` + chuẩn hoá — không phụ thuộc `response.parsed` vốn đổi theo phiên
        bản SDK) cùng `usage_metadata` để cộng token vào lượt chat.
        """
        from google.genai import types

        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        return (response.text or ""), getattr(response, "usage_metadata", None)

    # --- Upload file (Files API) --------------------------------------------
    def upload_file(self, file_bytes: bytes, mime_type: str | None) -> tuple[str, str]:
        """Đẩy bytes file lên **Gemini Files API**, trả `(file_uri, mime_type)`.

        Dùng cho luồng chat đính kèm file: file upload 1 lần, lấy URI để gắn vào
        message qua `types.Part.from_uri` (Gemini đọc file native, không cần extract
        text). `mime_type` phải là loại Gemini đọc được (PDF/ảnh…); Word cần convert
        PDF trước. Raise nếu upload lỗi — caller tự fail-safe.
        """
        import io

        kwargs: dict[str, Any] = {"file": io.BytesIO(file_bytes)}
        if mime_type:
            kwargs["config"] = {"mime_type": mime_type}
        uploaded = self._client.files.upload(**kwargs)
        return (uploaded.uri or ""), (uploaded.mime_type or mime_type or "")

    # --- Embedding -----------------------------------------------------------
    def _embed_config(self, dims: int, task_type: str):
        from google.genai import types

        return types.EmbedContentConfig(output_dimensionality=dims, task_type=task_type)

    def embed(self, texts: list[str], dims: int, task_type: str) -> list[list[float]]:
        """Embed `texts` bằng `embedding_model`, trả vector thô theo đúng thứ tự.

        KHÔNG normalize/lọc chiều — đó là việc của caller (gemini-embedding-001
        ở <3072 chiều không normalize sẵn). `task_type` phải khớp phía dùng:
        RETRIEVAL_DOCUMENT lúc index, RETRIEVAL_QUERY lúc truy hồi.
        """
        response = self._client.models.embed_content(
            model=self.embedding_model,
            contents=texts,
            config=self._embed_config(dims, task_type),
        )
        return [list(emb.values or []) for emb in (response.embeddings or [])]

    async def aembed(self, texts: list[str], dims: int, task_type: str) -> list[list[float]]:
        """Bản async của `embed` (cho LightRAG embedding_func)."""
        response = await self._client.aio.models.embed_content(
            model=self.embedding_model,
            contents=texts,
            config=self._embed_config(dims, task_type),
        )
        return [list(emb.values or []) for emb in (response.embeddings or [])]
