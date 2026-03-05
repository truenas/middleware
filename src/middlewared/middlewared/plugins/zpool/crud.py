import typing

from middlewared.api import api_method
from middlewared.api.current import (
    ZPoolEntry,
    ZPoolQueryArgs,
    ZPoolQueryResult,
)
from middlewared.service import private, Service
from middlewared.service.decorators import pass_thread_local_storage

from .query_impl import query_impl


class ZPoolService(Service):

    class Config:
        namespace = "zpool"
        cli_private = True
        entry = ZPoolEntry

    @private
    @pass_thread_local_storage
    def query_impl(self, tls: typing.Any, data: dict | None = None) -> list[dict[str, typing.Any]]:
        if data is None:
            data = {}
        return query_impl(tls.lzh, data)

    @api_method(
        ZPoolQueryArgs,
        ZPoolQueryResult,
        roles=["POOL_READ"],
    )
    def query(self, data: dict) -> list[ZPoolEntry]:
        """Query ZFS pools with flexible options for properties, topology, scan, and features."""
        return [
            ZPoolEntry(**pool)
            for pool in self.middleware.call_sync('zpool.query_impl', data)
        ]
