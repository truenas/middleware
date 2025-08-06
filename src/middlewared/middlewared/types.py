"""Module for shared internal types not used in API validation."""
from types import TracebackType
from typing import TypeAlias


ExcInfo: TypeAlias = tuple[type[BaseException], BaseException, TracebackType]
OptExcInfo: TypeAlias = ExcInfo | tuple[None, None, None]
"""The return type of `sys.exc_info()`"""
