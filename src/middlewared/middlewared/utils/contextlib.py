# -*- coding=utf-8 -*-
import contextlib
import logging
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

__all__ = ["asyncnullcontext"]


@contextlib.asynccontextmanager
async def asyncnullcontext[T](enter_result: T = None) -> AsyncIterator[T]:
    yield enter_result
