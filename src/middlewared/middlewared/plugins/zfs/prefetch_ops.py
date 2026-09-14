from __future__ import annotations

from typing import TYPE_CHECKING, Any

import truenas_pylibzfs

from middlewared.service_exception import CallError
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


def prefetch(tls: Any, pool_name: str) -> None:
    try:
        pool = tls.lzh.open_pool(name=pool_name)
        pool.prefetch()
    except truenas_pylibzfs.ZFSException as e:
        raise CallError(str(e), e.code)


def prefetch_pools(context: ServiceContext) -> None:
    # query_imported_fast_impl avoids the much heavier pool service for what is only a
    # list of names. A failure on one pool must not stop the rest from being prefetched.
    for pool_info in query_imported_fast_impl().values():
        if pool_info["name"] in BOOT_POOL_NAME_VALID:
            continue

        try:
            context.logger.info("Prefetching metadata for %r pool", pool_info["name"])
            context.call_sync2(context.s.zfs.resource.pool.prefetch, pool_info["name"])
        except Exception as e:
            context.logger.error("Failed to prefetch metadata for pool %r: %s", pool_info["name"], e)
