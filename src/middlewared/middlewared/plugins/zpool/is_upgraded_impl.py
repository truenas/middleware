import typing

from .get_zpool_features_impl import get_zpool_features_impl

__all__ = ("is_upgraded_impl",)


def is_upgraded_impl(lzh: typing.Any, pool_name: str) -> bool:
    """Check whether all feature flags on `pool_name` are ENABLED or ACTIVE.

    Args:
        lzh: libzfs handle providing ``open_pool()``.
        pool_name: Name of the zpool to inspect.

    Returns:
        True when every feature flag is ENABLED or ACTIVE, False otherwise.
    """
    for feat, info in get_zpool_features_impl(lzh, pool_name).items():
        if info.state not in ('ENABLED', 'ACTIVE'):
            return False
    return True
