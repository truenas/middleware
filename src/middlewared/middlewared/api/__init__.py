from .base.decorator import api_method, private_method
from .base.event import Event

API_LOADING_FORBIDDEN = False

__all__ = ["api_method", "private_method", "Event", "API_LOADING_FORBIDDEN"]
