"""Controllers của module Example — re-export để routes import gọn.

Example là template chưa version hóa API (`/api/examples/`) nên để phẳng ở đây
thay vì gom theo `v1/` như chatbot.
"""

from .example_controller import ExampleController

__all__ = ["ExampleController"]
