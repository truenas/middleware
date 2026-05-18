from truenas_pylibzfs import libzfs_types

__all__ = ("is_upgraded_impl",)


def is_upgraded_impl(features: dict[str, libzfs_types.struct_zpool_feature]) -> bool:
    """Return whether every ZFS feature flag on a pool is enabled.

    Takes the mapping produced by ``get_zpool_features_impl`` and reports
    ``True`` only when each feature's state is ``ENABLED`` or ``ACTIVE``.
    """
    for info in features.values():
        if info.state not in ("ENABLED", "ACTIVE"):
            return False
    return True
