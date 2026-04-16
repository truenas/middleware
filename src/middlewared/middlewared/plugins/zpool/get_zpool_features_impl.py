from truenas_pylibzfs import libzfs_types

__all__ = ("get_zpool_features_impl",)


def get_zpool_features_impl(lzh: libzfs_types.ZFS, pool_name: str) -> dict[str, libzfs_types.struct_zpool_feature]:
    """Return all feature flags and their states for a zpool.

    Opens the pool by name and retrieves the full set of known ZFS
    feature flags. Each entry maps a feature name to a struct with
    guid, description, and state fields.

    Args:
        lzh: libzfs handle providing ``open_pool()``.
        pool_name: Name of the zpool to inspect.

    Returns:
        A dict mapping feature names to struct_zpool_feature entries
        (e.g. {'async_destroy': struct_zpool_feature(state='ENABLED', ...)}).
    """
    return lzh.open_pool(name=pool_name).get_features()
