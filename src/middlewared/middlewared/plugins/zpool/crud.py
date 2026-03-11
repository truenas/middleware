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

        This method provides an interface for retrieving information \
        about imported ZFS pools, including their health status, properties, vdev \
        topology, scan/scrub history, expansion state, and feature flags. The query \
        can be scoped to specific pools and customized to include only the data needed.

        Args:
            data (dict): Dictionary containing query parameters:
                - pool_names (list[str] | None): Pool names to query. If None (default), \
                    all imported pools are returned.
                - properties (list[str] | None): ZFS property names to retrieve (e.g., \
                    "size", "capacity", "health"). If None (default), no properties are returned.
                - topology (bool): Include vdev topology (data, log, cache, spares, \
                    special, dedup, and stripe vdevs). Default: False.
                - scan (bool): Include most recent scrub or resilver information. Default: False.
                - expand (bool): Include active pool expansion information. Default: False.
                - features (bool): Include pool feature flags. Default: False.

        Returns:
            list[ZPoolEntry]: List of pool entries, each containing:
                - name, guid, status, healthy, warning, status_code, status_detail
                - properties (if requested): dict of property names to values with source info
                - topology (if requested): vdev tree organized by type
                - scan (if requested): scrub/resilver state, progress, and timing
                - expand (if requested): expansion state information
                - features (if requested): list of feature flags with state

        Examples:
            # Query all pools (minimal info: name, guid, status, health)
            query({})

            # Query specific pools with properties
            query({"pool_names": ["tank", "boot-pool"], "properties": ["size", "capacity"]})

            # Query with full topology and scan information
            query({"pool_names": ["tank"], "topology": True, "scan": True})

            # Query everything
            query({"topology": True, "scan": True, "expand": True, "features": True, \
                "properties": ["size", "capacity", "health"]})
        """
        rv = list()
        for pool in self.middleware.call_sync("zpool.query_impl", data):
            rv.append(ZPoolEntry(**pool))
        return rv
