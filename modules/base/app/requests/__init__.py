"""
Request (validation) layer cho module mới — bản Django của
`Modules/Base/app/Http/Requests`.

  - base_form_request.py → FormRequestMixin, BaseFormRequest  (≈ BaseFormDataRequestV2)

Import gọn: `from modules.base.app.requests import BaseFormRequest, FormRequestMixin`.
"""

from .base_form_request import BaseFormRequest, FormRequestMixin

__all__ = ["BaseFormRequest", "FormRequestMixin"]
