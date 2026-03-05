import typing

from truenas_pylibzfs import ZPOOLProperty

__all__ = ("get_zpool_status_impl",)


def get_zpool_status_impl(pool: typing.Any) -> dict:
    """Return health and status information for a pool.

    Reads the pool's health property and zpool status to produce a
    dict with status classification fields used by the middleware.

    Args:
        pool: An already-opened pylibzfs pool object.

    Returns:
        A dict with keys: health (str), status (ZPOOLStatus enum),
        reason (str|None), action (str|None), message (str|None).
    """
    status_struct = pool.status(get_stats=False)
    health_prop = pool.get_properties(properties={ZPOOLProperty.HEALTH}).health
    return {
        "health": health_prop.value,
        "zpool_status": status_struct.status,
        "reason": status_struct.reason,
        "action": status_struct.action,
        "message": status_struct.message,
    }
