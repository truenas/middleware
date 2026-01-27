from __future__ import annotations

from logging import Logger
from typing import Any, Callable, Coroutine, TYPE_CHECKING

from middlewared.utils.service.call_mixin import CallMixin

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("ServiceContext",)


class ServiceContext(CallMixin):
    def __init__(self, middleware: Middleware, logger: Logger):
        self.middleware = middleware
        self.logger = logger

    async def to_thread[**P, T](self, f: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        return await self.middleware.run_in_thread(f, *args, **kwargs)

    def run_coroutine[T](self, coro: Coroutine[Any, Any, T]) -> T:
        return self.middleware.run_coroutine(coro)
