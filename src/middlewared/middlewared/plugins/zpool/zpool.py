from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import Event, api_method
from middlewared.api.current import (
    ZPoolCreate,
    ZPoolCreateArgs,
    ZPoolCreateResult,
    ZPoolEntry,
    ZPoolQuery,
    ZPoolQueryAddedEvent,
    ZPoolQueryArgs,
    ZPoolQueryChangedEvent,
    ZPoolQueryRemovedEvent,
    ZPoolQueryResult,
)
from middlewared.service import Service, job, private
from middlewared.service.decorators import pass_thread_local_storage

from . import zpool_create as _create
from . import zpool_query as _query
from .create_impl import create_impl
from .get_zpool_disks_impl import get_zpool_disks_impl
from .get_zpool_features_impl import get_zpool_features_impl
from .is_upgraded_impl import is_upgraded_impl
from .scrub import ZpoolScrubService
from .status_impl import status_impl
from .upgrade_zpool_impl import upgrade_zpool_impl

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware
    from middlewared.utils.types import EventType

__all__ = ("ZPoolService",)


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

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self.scrub = ZpoolScrubService(middleware)

    @private
    @pass_thread_local_storage
    def query_impl(self, tls: Any, data: ZPoolQuery) -> list[dict[str, Any]]:
        return _query.query_impl(tls, data)

    @api_method(ZPoolQueryArgs, ZPoolQueryResult, roles=["POOL_READ"], check_annotations=True)
    def query(self, data: ZPoolQuery) -> list[ZPoolEntry]:
        """
        Query ZFS pools with flexible options for properties, topology, scan, and features.

        Returns information about both imported and non-imported pools. By default,
        only minimal data is returned (name, guid, status, health); additional
        sections like topology, scan, properties, etc. must be opted into via
        their respective flags. Pools that exist in the database but are not
        currently imported are returned with an OFFLINE status.

        The boot pool can be queried by explicitly passing its name in ``pool_names``.
        It is excluded from results when ``pool_names`` is null (query-all mode).

        Examples:

        Query all pools (minimal info: name, guid, status, health):

        .. code:: json

            {}

        Query specific pools with properties:

        .. code:: json

            {"pool_names": ["tank", "boot-pool"], "properties": ["size", "capacity"]}

        Query with full topology and scan information:

        .. code:: json

            {"pool_names": ["tank"], "topology": true, "scan": true}

        Query everything:

        .. code:: json

            {
                "topology": true,
                "scan": true,
                "expand": true,
                "features": true,
                "properties": ["size", "capacity", "health"]
            }
        """
        return _query.query(self.context, data)

    @private
    def send_change_event(self, pool_name: str, event_type: EventType = "CHANGED") -> None:
        _query.send_change_event(self.context, pool_name, event_type)

    @private
    def send_removed_event(self, pool_id: int) -> None:
        """Emit a ``zpool.query`` REMOVED event for the given database id."""
        self.middleware.send_event("zpool.query", "REMOVED", id=pool_id)

    @private
    @pass_thread_local_storage
    def create_impl(
        self,
        tls: Any,
        name: str,
        vdevs: list[dict[str, Any]],
        properties: dict[str, str],
        filesystem_properties: dict[str, str],
        force: bool,
    ) -> None:
        create_impl(tls.lzh, name, vdevs, properties, filesystem_properties, force)

    @api_method(
        ZPoolCreateArgs,
        ZPoolCreateResult,
        roles=["POOL_WRITE"],
        audit="Pool create",
        audit_extended=lambda data: data["name"],
        check_annotations=True,
    )
    @job(lock="pool_createupdate")
    def create(self, job: Job, data: ZPoolCreate) -> ZPoolEntry:
        """
        Create a ZFS pool, as ``zpool create`` does.

        ``topology`` is the vdev grammar of ``zpool create`` keyed the way :method:`zpool.query` reports it,
        ``properties`` are ``-o`` pool properties and ``filesystem_properties`` are ``-O`` root filesystem
        properties, all given by native name and handed to ZFS as-is. Fields left null take the TrueNAS
        defaults. The pool is created through ``truenas_pylibzfs`` and returned as :method:`zpool.query`
        reports it, so the entry reflects the values as canonicalized by ZFS, not the input.

        Every disk referenced by the topology is formatted first, so a disk that is currently in use fails
        validation before any disk is touched. On an HA system this must run on the active controller.

        Encrypted pool roots are not created here; use :method:`zfs.resource.create` to add encrypted datasets
        to the pool afterwards.

        .. versionadded:: 27.0.0

        Create a pool named "tank": RAIDZ1 with three disks, one cache disk, one log disk, and one hot spare,
        with periodic TRIM enabled and deduplication on its root filesystem:

        .. code:: json

            {
                "name": "tank",
                "topology": {
                    "data": [{"type": "raidz1", "disks": ["sda", "sdb", "sdc"]}],
                    "log": [{"type": "disk", "disks": ["sdd"]}],
                    "cache": ["sde"],
                    "spares": ["sdf"]
                },
                "properties": {"autotrim": "on"},
                "filesystem_properties": {"dedup": "on"}
            }
        """
        return _create.create(self.context, job, data)

    @private
    def status(self, name: str | None = None, real_paths: bool = False) -> dict[str, Any]:
        """The equivalent of running 'zpool status' from the cli.

        Args:
            name: restrict the output to this pool; every imported pool otherwise.
            real_paths: resolve the underlying devices to their real device
                (i.e. /dev/disk/by-id/blah -> /dev/sda1).

        An example of what this returns looks like the following:
            {
              "disks": {
                "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec": {
                  "pool_name": "evo",
                  "disk_status": "ONLINE",
                  "disk_read_errors": 0,
                  "disk_write_errors": 0,
                  "disk_checksum_errors": 0,
                  "vdev_name": "stripe",
                  "vdev_type": "data",
                  "vdev_disks": [
                    "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec"
                  ]
                }
              },
              "pools": {
                "evo": {
                    "spares": {},
                    "logs": {},
                    "dedup": {},
                    "special": {},
                    "l2cache": {},
                    "data": {
                        "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec": {
                            "pool_name": "evo",
                            "disk_status": "ONLINE",
                            "disk_read_errors": 0,
                            "disk_write_errors": 0,
                            "disk_checksum_errors": 0,
                            "vdev_name": "stripe",
                            "vdev_type": "data",
                            "vdev_disks": [
                            "/dev/disk/by-partuuid/d9cfa346-8623-402f-9bfe-a8256de902ec"
                            ]
                        }
                    }
                }
            }
        """
        return status_impl(name, real_paths)

    @private
    @pass_thread_local_storage
    def get_disks(self, tls: Any, pool_name: str) -> list[str]:
        """Whole-disk device names (e.g. sda, nvme0n1) backing every vdev of an imported pool."""
        return get_zpool_disks_impl(tls.lzh, pool_name)

    @private
    @pass_thread_local_storage
    def is_upgraded(self, tls: Any, pool_name: str) -> bool:
        """Whether every ZFS feature flag on an imported pool is ENABLED or ACTIVE."""
        return is_upgraded_impl(get_zpool_features_impl(tls.lzh, pool_name))

    @private
    @pass_thread_local_storage
    def upgrade(self, tls: Any, pool_name: str) -> None:
        """Enable every supported ZFS feature flag on an imported pool."""
        upgrade_zpool_impl(tls.lzh, pool_name)
