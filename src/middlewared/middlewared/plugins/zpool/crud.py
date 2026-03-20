import threading

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
    def query_impl(
        self, tls: threading.local, data: dict | None = None
    ) -> list[ZPoolEntry]:
        if data is None:
            data = dict()
        return query_impl(tls.lzh, data)

    @api_method(
        ZPoolQueryArgs,
        ZPoolQueryResult,
        roles=["POOL_READ"],
    )
    def query(self, data: dict) -> list[ZPoolEntry]:
        """
        Query ZFS pools with flexible options for properties, topology, scan, and features.

        This method provides an interface for retrieving information
        about imported ZFS pools, including their health status, properties, vdev
        topology, scan/scrub history, expansion state, and feature flags. The query
        can be scoped to specific pools and customized to include only the data needed.

        Examples::

            # Query all pools (minimal info: name, guid, status, health)
            {}

            # Query specific pools with properties
            {
                "pool_names": ["tank", "boot-pool"],
                "properties": ["size", "capacity"]
            }

            # Query with full topology and scan information
            {
                "pool_names": ["tank"],
                "topology": true,
                "scan": true
            }

            # Query everything
            {
                "topology": true,
                "scan": true,
                "expand": true,
                "features": true,
                "properties": ["size", "capacity", "health"]
            }
        """
        rv = list()
        for pool in self.middleware.call_sync("zpool.query_impl", data):
            rv.append(ZPoolEntry(**pool))
        return rv
