from collections.abc import Iterator
import contextlib
import threading
from typing import Any

from truenas_pylibzfs import ZFSException

from middlewared.api import Event, api_method
from middlewared.api.current import (
    ZPoolEntry,
    ZPoolOffline,
    ZPoolOfflineArgs,
    ZPoolOfflineResult,
    ZPoolOnline,
    ZPoolOnlineArgs,
    ZPoolOnlineResult,
    ZPoolQueryAddedEvent,
    ZPoolQueryArgs,
    ZPoolQueryChangedEvent,
    ZPoolQueryRemovedEvent,
    ZPoolQueryResult,
)
from middlewared.service import CallError, Service, ValidationError, private
from middlewared.service.decorators import pass_thread_local_storage

from .device_state_impl import offline_impl, online_impl
from .exceptions import (
    ZpoolNotFoundException,
    ZpoolVdevIsCacheException,
    ZpoolVdevIsSpareException,
    ZpoolVdevNotDiskException,
    ZpoolVdevNotFoundException,
)
from .query_impl import query_impl

# Properties baked into every emitted `zpool.query` event so that subscribers
# receive a Pool-shaped payload without having to round-trip another call.
EVENT_PROPERTIES = (
    "class_normal_used",
    "class_normal_available",
    "class_normal_usable",
    "class_special_used",
    "class_special_available",
    "class_special_usable",
    "autotrim",
    "dedup_table_size",
    "dedup_table_quota",
)


@contextlib.contextmanager
def vdev_state_errors(schema: str) -> Iterator[None]:
    try:
        yield
    except ZpoolNotFoundException as e:
        raise ValidationError(f"{schema}.pool_name", str(e), e.errno)
    except (
        ZpoolVdevNotFoundException,
        ZpoolVdevNotDiskException,
        ZpoolVdevIsCacheException,
        ZpoolVdevIsSpareException,
    ) as e:
        raise ValidationError(f"{schema}.vdev_guid", str(e), e.errno)
    except ZFSException as e:
        raise CallError(f"{e.action}: {e.description}")


class ZPoolService(Service):
    class Config:
        namespace = "zpool"
        cli_private = True
        entry = ZPoolEntry
        events = [
            Event(
                name="zpool.query",
                description="Sent on zpool changes.",
                roles=["POOL_READ"],
                models={
                    "ADDED": ZPoolQueryAddedEvent,
                    "CHANGED": ZPoolQueryChangedEvent,
                    "REMOVED": ZPoolQueryRemovedEvent,
                },
            )
        ]

    @private
    @pass_thread_local_storage
    def query_impl(self, tls: threading.local, data: dict | None = None) -> list[dict[str, Any]]:
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
                    "id": pool_info["id"] if pool_info else None,
                    "name": name,
                    "guid": int(pool_info["guid"]) if pool_info else 0,
                    "status": "OFFLINE",
                    "healthy": False,
                    "warning": False,
                    "status_code": status_code,
                    "status_detail": status_detail,
                    "is_upgraded": None,
                    "all_sed": pool_info.get("all_sed"),
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
        boot_pool_name = self.call_sync2(self.s.boot.pool_name)
        requested_names = data.get("pool_names")

        db_pools = {}
        pool_names = []
        for p in self.middleware.call_sync("datastore.query", "storage.volume", [], {"prefix": "vol_"}):
            if requested_names is None or p["name"] in requested_names:
                db_pools[p["name"]] = p
                pool_names.append(p["name"])

        # Boot pool is never in the database but can be explicitly requested.
        if requested_names is not None and boot_pool_name in requested_names:
            pool_names.append(boot_pool_name)

        results = self.middleware.call_sync("zpool.query_impl", data | {"pool_names": pool_names})
        for entry in results:
            entry.update({"id": None, "all_sed": None})
            db_entry = db_pools.get(entry["name"])
            if db_entry is not None:
                entry.update({"id": db_entry["id"], "all_sed": db_entry["all_sed"]})

        imported_names = {p["name"] for p in results}
        offline_names = [name for name in pool_names if name not in imported_names]
        results.extend(self.offline_entries(db_pools, offline_names))

        rv = []
        for pool in results:
            rv.append(ZPoolEntry(**pool))
        return rv

    @api_method(
        ZPoolOfflineArgs,
        ZPoolOfflineResult,
        roles=["POOL_WRITE"],
        audit="Disk offline",
        audit_extended=lambda data: f"{data['vdev_guid']} in {data['pool_name']!r} pool",
        check_annotations=True,
    )
    @pass_thread_local_storage
    def offline(self, tls, data: ZPoolOffline) -> None:
        """
        Take a disk of a pool offline, as ``zpool offline`` does.

        ZFS stops reading from and writing to the disk until :method:`zpool.online` brings it back, and the
        offline state persists across reboots and pool imports. The disk is named by its ``guid`` from the
        ``topology`` of :method:`zpool.query`.

        A validation error is raised when the pool or the disk does not exist, when the GUID names a vdev that
        is not a disk (a mirror, a RAIDZ or dRAID group, or a dRAID distributed spare), when the disk is a hot
        spare that is not in use, or when it is a cache device, which ZFS cannot bring back online on a pool
        whose ``autoexpand`` property is on. ZFS refuses to take a disk offline when the pool would have no
        valid replica of its data left.

        .. versionadded:: 28.0.0

        Example:

        .. code:: json

            {"pool_name": "tank", "vdev_guid": "80802394992848654"}
        """
        with vdev_state_errors("zpool.offline"):
            offline_impl(tls.lzh, data.pool_name, data.vdev_guid)

    @api_method(
        ZPoolOnlineArgs,
        ZPoolOnlineResult,
        roles=["POOL_WRITE"],
        audit="Disk online",
        audit_extended=lambda data: f"{data['vdev_guid']} in {data['pool_name']!r} pool",
        check_annotations=True,
    )
    @pass_thread_local_storage
    def online(self, tls, data: ZPoolOnline) -> None:
        """
        Bring a disk of a pool back online, as ``zpool online`` does.

        The disk is named by its ``guid`` from the ``topology`` of :method:`zpool.query`. ZFS resilvers whatever
        was written to the pool while the disk was offline. The call can succeed while the disk stays unusable,
        so check afterwards that its ``state`` in :method:`zpool.query` is ``ONLINE``.

        A validation error is raised when the pool or the disk does not exist, when the GUID names a vdev that
        is not a disk (a mirror, a RAIDZ or dRAID group, or a dRAID distributed spare), or when the disk is a hot
        spare that is not in use.

        .. versionadded:: 28.0.0

        Example:

        .. code:: json

            {"pool_name": "tank", "vdev_guid": "80802394992848654"}
        """
        with vdev_state_errors("zpool.online"):
            online_impl(tls.lzh, data.pool_name, data.vdev_guid)

    @private
    def send_change_event(self, pool_name: str, event_type: str = "CHANGED"):
        """Emit a ``zpool.query`` event with a Pool-shaped payload.

        Re-queries ``zpool.query`` with topology, scan, and the standard
        property set so subscribers receive the same fields they would
        from a direct call. No-ops when the pool is not in the database
        (boot pool, or a pool that has been exported between the trigger
        and the emit).
        """
        pools = self.middleware.call_sync(
            "zpool.query",
            {
                "pool_names": [pool_name],
                "topology": True,
                "scan": True,
                "properties": list(EVENT_PROPERTIES),
            },
        )
        if not pools:
            return
        pool = pools[0].model_dump()
        if pool["id"] is None:
            return
        self.middleware.send_event("zpool.query", event_type, id=pool["id"], fields=pool)

    @private
    def send_removed_event(self, pool_id: int):
        """Emit a ``zpool.query`` REMOVED event for the given database id."""
        self.middleware.send_event("zpool.query", "REMOVED", id=pool_id)
