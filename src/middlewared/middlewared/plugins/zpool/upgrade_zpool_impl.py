import typing

__all__ = ("upgrade_zpool_impl",)


def upgrade_zpool_impl(lzh: typing.Any, pool_name: str) -> None:
    pool = lzh.open_pool(name=pool_name)
    pool.upgrade()
