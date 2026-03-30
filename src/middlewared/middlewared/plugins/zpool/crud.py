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

    @private
    def offline_entries(self, db_pools, offline_names):
        """Build OFFLINE ZPoolEntry dicts for pools not currently imported.

        For pools flagged as all-SED in the database, checks whether locked
        SED disks may explain the import failure and sets status_code and
        status_detail accordingly. The SED check is performed at most once
        per call and reused across all offline all-SED pools.
        """
        entries = []
        sed_cache = {}
        for name in offline_names:
            pool_info = db_pools.get(name, {})
            status_code = None
            status_detail = None

            if pool_info.get("all_sed"):
                if not sed_cache:
                    sed_enabled = self.middleware.call_sync("system.sed_enabled")
                    locked_sed_disks = set()
                    if sed_enabled:
                        for disk in self.middleware.call_sync(
                            "disk.query",
                            [["sed_status", "=", "LOCKED"]],
                            {"extra": {"sed_status": True}},
                        ):
                            locked_sed_disks.add(disk["name"])
                    sed_cache.update(
                        {
                            "sed_enabled": sed_enabled,
                            "locked_sed_disks": locked_sed_disks,
                        }
                    )

                if sed_cache["sed_enabled"] and sed_cache["locked_sed_disks"]:
                    status_code = "LOCKED_SED_DISKS"
                    status_detail = (
                        "Pool might have failed to import because of "
                        f"{', '.join(sed_cache['locked_sed_disks'])!r} SED disk(s) being locked"
                    )

            entries.append(
                {
                    "name": name,
                    "guid": int(pool_info["guid"]) if pool_info else 0,
                    "status": "OFFLINE",
                    "healthy": False,
                    "warning": False,
                    "status_code": status_code,
                    "status_detail": status_detail,
                }
            )
        return entries

    @api_method(
        ZPoolQueryArgs,
        ZPoolQueryResult,
        roles=["POOL_READ"],
    )
    def query(self, data: dict) -> list[ZPoolEntry]:
        """
        Query ZFS pools with flexible options for properties, topology, scan, and features.

        Returns information about both imported and non-imported pools. By default,
        only minimal data is returned (name, guid, status, health); additional
        sections like topology, scan, properties, etc. must be opted into via
        their respective flags. Pools that exist in the database but are not
        currently imported are returned with an OFFLINE status.

        The boot pool can be queried by explicitly passing its name in ``pool_names``.
        It is excluded from results when ``pool_names`` is null (query-all mode).

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
        boot_pool_name = self.middleware.call_sync("boot.pool_name")
        requested_names = data.get("pool_names")

        db_pools = {}
        pool_names = []
        for p in self.middleware.call_sync(
            "datastore.query", "storage.volume", [], {"prefix": "vol_"}
        ):
            if requested_names is None or p["name"] in requested_names:
                db_pools[p["name"]] = p
                pool_names.append(p["name"])

        # Boot pool is never in the database but can be explicitly requested.
        if requested_names is not None and boot_pool_name in requested_names:
            pool_names.append(boot_pool_name)

        results = self.middleware.call_sync(
            "zpool.query_impl", data | {"pool_names": pool_names}
        )
        imported_names = {p["name"] for p in results}
        offline_names = [name for name in pool_names if name not in imported_names]
        results.extend(self.offline_entries(db_pools, offline_names))

        rv = []
        for pool in results:
            rv.append(ZPoolEntry(**pool))
        return rv
