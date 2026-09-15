from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.service import Service
from middlewared.service.decorators import pass_thread_local_storage

from . import prefetch_ops as _ops

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("ZFSResourcePoolPrefetchService",)


class ZFSResourcePoolPrefetchService(Service):

    class Config:
        namespace = "zfs.resource.pool"
        private = True

    @pass_thread_local_storage
    def prefetch(self, tls: Any, pool_name: str) -> None:
        """
        Prefetch pool metadata (DDT and BRT) into ARC.

        Loads both the Deduplication Table (DDT) and Block Reference Table (BRT)
        into the ARC to reduce latency of subsequent operations. This is equivalent
        to running 'zpool prefetch <pool>' without the -t flag.
        """
        _ops.prefetch(tls, pool_name)

    def prefetch_pools(self) -> None:
        """
        Prefetch metadata for all imported pools (excluding boot pools).
        """
        _ops.prefetch_pools(self.context)


async def pool_post_import(middleware: Middleware, pool: dict[str, Any] | None) -> None:
    if pool:
        middleware.create_task(middleware.call2(middleware.services.zfs.resource.pool.prefetch, pool["name"]))
    else:
        # During boot, pool.post_import is called once with None after all pools
        # are imported as a batch. For user-initiated imports, it is called per pool
        # with the pool dictionary. Handle both invocation patterns accordingly.
        middleware.create_task(middleware.call2(middleware.services.zfs.resource.pool.prefetch_pools))


async def setup(middleware: Middleware) -> None:
    middleware.register_hook("pool.post_import", pool_post_import)
