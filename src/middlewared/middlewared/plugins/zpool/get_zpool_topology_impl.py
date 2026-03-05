import typing

__all__ = ("get_zpool_topology_impl",)


def get_zpool_topology_impl(pool: typing.Any) -> typing.Any:
    """Return the full vdev topology for a pool.

    Calls pool.status(get_stats=True) which returns a struct_zpool_status
    containing storage_vdevs, support_vdevs, and spares with full stats.

    Args:
        pool: An already-opened pylibzfs pool object.

    Returns:
        A struct_zpool_status with vdev topology and statistics.
    """
    return pool.status(get_stats=True)
