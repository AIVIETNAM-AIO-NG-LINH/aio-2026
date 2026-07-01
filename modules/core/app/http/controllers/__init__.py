"""Controllers của module Core — re-export để routes import gọn.

Core chỉ có endpoint hạ tầng (health-check), không version hóa như chatbot nên
để phẳng ở đây thay vì gom theo `v1/`.
"""

from .health_controller import HealthController

__all__ = ["HealthController"]
