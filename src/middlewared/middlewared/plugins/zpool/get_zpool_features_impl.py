import typing

__all__ = ("get_zpool_features_impl",)


def get_zpool_features_impl(lzh: typing.Any, pool_name: str) -> dict:
    return lzh.open_pool(name=pool_name).get_features()
