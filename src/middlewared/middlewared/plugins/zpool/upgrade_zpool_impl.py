import typing

__all__ = ("upgrade_zpool_impl",)


def upgrade_zpool_impl(lzh: typing.Any, pool_name: str) -> None:
    """Enable all supported ZFS feature flags on `pool_name`."""
    pool = lzh.open_pool(name=pool_name)
    pool.upgrade()
