"""Translate helper — bản Django của `Modules\\Translation\\Support\\TranslateHelper`.

Bên Laravel: tra bản dịch theo khoá `namespace.name` từ cache theo ngôn ngữ của
actor hiện tại, miss → thử ngôn ngữ fallback trực tiếp (1 cấp), vẫn miss → trả
`text` gốc; cuối cùng nội suy biến `{(name)}` từ `data`.

Bản này MỚI LÀ STUB: chưa có Language/TranslateCache nên trả thẳng `text` —
call-site cứ gọi như thật, khi nào port xong phần dịch thì thay ruột hàm.

Hai biến thể (chọn theo THỜI ĐIỂM evaluate, mirror ngữ nghĩa Laravel — `messages()`
chạy mỗi request nên i18n() luôn per-request):
  - `translate`      — gọi tại runtime (raise exception, build response, SSE event).
  - `translate_lazy` — cho chuỗi khai báo ở class-attribute (vd `error_messages`
    của serializer field, `invalid_data_message`): evaluate lúc import là SAI ngôn
    ngữ khi có bản dịch thật → proxy lazy chỉ resolve khi chuỗi được dùng (per-request).
"""

from __future__ import annotations

from django.utils.functional import lazy


def translate(
    text: str,
    key: str,
    data: dict[str, str] | None = None,
    user_id: int | None = None,
    get_lang_header: bool = False,
) -> str:
    """Dịch 1 chuỗi theo khoá `namespace.name`. `text` là base (EN) — vừa là chuỗi
    hiển thị mặc định, vừa là fallback khi miss / không có khoá.

    Stub: trả thẳng `text`, chưa tra cache / nội suy `{(name)}`.
    """
    return text


#: Bản lazy của {@translate} — trả proxy, chỉ gọi `translate()` thật khi chuỗi được
#: ép về str (lúc render lỗi/response, tức per-request). Dùng cho chuỗi khai báo ở
#: class-attribute; chuỗi tại runtime thì gọi thẳng `translate()`.
translate_lazy = lazy(translate, str)
