import asyncio
import json
import typing

__all__ = (
    "dumps",
    "loads",
)


async def dumps(obj: typing.Any, **kwargs) -> str:
    """
    Async wrapper for json.dumps() that offloads serialization to a thread pool.

    Use this instead of json.dumps() in async contexts to prevent event loop blocking
    when serializing large objects.

    Args:
        obj: Python object to serialize
        **kwargs: Additional arguments passed to json.dumps()

    Returns:
        JSON string
    """
    return await asyncio.to_thread(json.dumps, obj, **kwargs)


async def loads(s: str | bytes, **kwargs) -> typing.Any:
    """
    Async wrapper for json.loads() that offloads parsing to a thread pool.

    Use this instead of json.loads() in async contexts to prevent event loop blocking
    when parsing large JSON payloads.

    Args:
        s: JSON string or bytes to parse
        **kwargs: Additional arguments passed to json.loads()

    Returns:
        Parsed JSON data
    """
    return await asyncio.to_thread(json.loads, s, **kwargs)
