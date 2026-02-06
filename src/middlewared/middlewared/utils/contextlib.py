# -*- coding=utf-8 -*-
from collections.abc import AsyncGenerator
import contextlib
import logging

logger = logging.getLogger(__name__)

__all__ = ["asyncnullcontext"]


@contextlib.asynccontextmanager
async def asyncnullcontext[T](enter_result: T | None = None) -> AsyncGenerator[T | None]:
    yield enter_result
