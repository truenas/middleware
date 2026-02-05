"""Module for shared internal types not used in API validation."""
from types import TracebackType
from typing import Callable, Literal, TypeAlias

__all__ = ["AuditCallback", "JobProgressCallback", "EventType", "ExcInfo", "OptExcInfo"]

AuditCallback = Callable[[str], None]
JobProgressCallback = Callable[[dict], None] | None

EventType: TypeAlias = Literal['ADDED', 'CHANGED', 'REMOVED']

ExcInfo: TypeAlias = tuple[type[BaseException], BaseException, TracebackType]
OptExcInfo: TypeAlias = ExcInfo | tuple[None, None, None]
"""The return type of `sys.exc_info()`"""
