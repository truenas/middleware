from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.main import Middleware


class BaseServiceContainer:
    def __init__(self, middleware: Middleware):
        self.middleware = middleware
