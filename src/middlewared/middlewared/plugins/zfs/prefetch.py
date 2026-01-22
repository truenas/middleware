import typing

import truenas_pylibzfs

from middlewared.service import CallError, Service
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl


class ZFSResourcePoolPrefetchService(Service):

    class Config:
        namespace = 'zfs.resource.pool'
        private = True

    @pass_thread_local_storage
    def prefetch(self, tls: typing.Any, pool_name: str) -> None:
        """
        Prefetch pool metadata (DDT and BRT) into ARC.

        Loads both the Deduplication Table (DDT) and Block Reference Table (BRT)
        into the ARC to reduce latency of subsequent operations. This is equivalent
        to running 'zpool prefetch <pool>' without the -t flag.
        """
        try:
            pool = tls.lzh.open_pool(name=pool_name)
            pool.prefetch()
        except truenas_pylibzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    def prefetch_pools(self) -> None:
        """
        Prefetch metadata for all imported pools (excluding boot pools).

        This method iterates through all imported ZFS pools (excluding boot pools)
        and triggers metadata prefetch for each. It's designed to avoid excessive
        calls to the pool service by using the fast query implementation.

        Boot pools are automatically excluded from prefetch operations.
        Errors for individual pools are logged but don't stop the process.
        """
        for pool_info in query_imported_fast_impl().values():
            if pool_info['name'] in BOOT_POOL_NAME_VALID:
                continue

            try:
                self.logger.info('Prefetching metadata for %r pool', pool_info['name'])
                self.middleware.call_sync('zfs.resource.pool.prefetch', pool_info['name'])
            except Exception as e:
                self.logger.error('Failed to prefetch metadata for pool %r: %s', pool_info['name'], e)


async def pool_post_import(middleware: typing.Any, pool: dict[str, typing.Any] | None) -> None:
    if pool:
        middleware.create_task(middleware.call('zfs.resource.pool.prefetch', pool['name']))
    else:
        # During boot, pool.post_import is called once with None after all pools
        # are imported as a batch. For user-initiated imports, it is called per pool
        # with the pool dictionary. Handle both invocation patterns accordingly.
        middleware.create_task(middleware.call('zfs.resource.pool.prefetch_pools'))


async def setup(middleware: typing.Any) -> None:
    middleware.register_hook('pool.post_import', pool_post_import)
