# -*- coding=utf-8 -*-
import contextlib
import logging

logger = logging.getLogger(__name__)

__all__ = ["asyncnullcontext"]


@contextlib.asynccontextmanager
async def asyncnullcontext(enter_result=None):
    yield enter_result
