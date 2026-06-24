import errno
import os
import threading

from fenced.fence import ExitCode as FencedExitCodes
from truenas_pylibzfs import ZFSException

from middlewared.api import Event, api_method
from middlewared.api.current import (
    ZPoolCreateArgs,
    ZPoolCreateResult,
    ZPoolEntry,
    ZPoolQueryAddedEvent,
    ZPoolQueryArgs,
    ZPoolQueryChangedEvent,
    ZPoolQueryRemovedEvent,
    ZPoolQueryResult,
)
from middlewared.plugins.pool_.utils import UpdateImplArgs, ZPOOL_CACHE_FILE
from middlewared.plugins.zfs_.validation_utils import validate_pool_name
from middlewared.service import CallError, Service, ValidationErrors, job, private
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.utils.size import format_size

from .create_impl import (
    assemble_create_pool_vdev_kwargs,
    build_fs_properties,
    build_pool_properties,
    convert_topology_to_vdevs,
    validate_vdev_layout,
)
from .exceptions import ZpoolCreateException, ZpoolException
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
    def query_impl(self, tls: threading.local, data: dict | None = None) -> list[ZPoolEntry]:
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
        boot_pool_name = self.middleware.call_sync("boot.pool_name")
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

    @api_method(
        ZPoolCreateArgs,
        ZPoolCreateResult,
        roles=["POOL_WRITE"],
        audit="Pool create",
        audit_extended=lambda data: data["name"],
    )
    @job(lock="pool_createupdate")
    async def create(self, job, data):
        """
        Create a new ZFS pool.

        The pool is built from the supplied ``topology`` using the
        ``truenas_pylibzfs`` bindings. All disks referenced by the topology are
        formatted before the pool is created, so any disk currently in use will
        cause the call to fail. On an HA system this must run on the active
        controller.

        .. versionadded:: 27.0.0

        Example::

            {
                "name": "tank",
                "topology": {
                    "data": [{"type": "RAIDZ1", "disks": ["sda", "sdb", "sdc"]}],
                    "cache": [{"type": "STRIPE", "disks": ["sdd"]}],
                    "log": [{"type": "STRIPE", "disks": ["sde"]}],
                    "spares": ["sdf"]
                }
            }
        """
        verrors = ValidationErrors()
        name = data["name"]

        if await self.middleware.call("pool.query", [("name", "=", name)]):
            verrors.add("zpool_create.name", "A pool with this name already exists.", errno.EEXIST)
        elif not validate_pool_name(name):
            verrors.add("zpool_create.name", "Invalid pool name", errno.EINVAL)

        dedup_table_quota_value = None
        if data["deduplication"] == "ON":
            dedup_table_quota_value = await self.middleware.call(
                "pool.validate_dedup_table_quota", data, verrors, "zpool_create"
            )

        verrors.check()

        is_ha = await self.middleware.call("failover.licensed")
        if is_ha and (rc := await self.middleware.call("failover.fenced.start")):
            if rc == FencedExitCodes.ALREADY_RUNNING.value[0]:
                try:
                    await self.middleware.call("failover.fenced.signal", {"reload": True})
                except Exception:
                    self.logger.error("Unhandled exception reloading fenced", exc_info=True)
            else:
                err = "Unexpected error starting fenced"
                for i in filter(lambda x: x.value[0] == rc, FencedExitCodes):
                    err = i.value[1]
                raise CallError(err)

        for field, message in validate_vdev_layout(data["topology"]):
            verrors.add(f"zpool_create.{field}", message)
        verrors.check()

        disks, vdevs = convert_topology_to_vdevs(data["topology"])
        verrors.add_child(
            "zpool_create",
            await self.middleware.call("disk.check_disks_availability", list(disks), data["allow_duplicate_serials"]),
        )
        verrors.check()

        disks_cache = {i.name: {"size": i.size_bytes} for i in await self.middleware.call("disk.get_disks")}
        min_data_size = min(
            disks_cache[disk]["size"]
            for disk in sum([vdev["disks"] for vdev in data["topology"].get("data", [])], [])
            if disk in disks_cache
        )
        for spare_disk in data["topology"].get("spares") or []:
            spare_size = disks_cache[spare_disk]["size"]
            if spare_size < min_data_size:
                verrors.add(
                    "zpool_create.topology",
                    f"Spare {spare_disk} ({format_size(spare_size)}) is smaller than the smallest data disk "
                    f"({format_size(min_data_size)})",
                )
        verrors.check()

        if data["all_sed"]:
            await self.middleware.call(
                "disk.setup_sed_disks_for_pool", list(disks), "zpool_create.topology", data["all_sed"]
            )

        if osize := (await self.middleware.call("system.advanced.config"))["overprovision"]:
            if log_disks := {disk: osize
                             for disk in sum([vdev["disks"] for vdev in data["topology"].get("log", [])], [])}:
                # will log errors if there are any so it won't crash here (this matches CORE behavior)
                await (await self.middleware.call("disk.resize", log_disks, True)).wait()

        await self.middleware.call("pool.format_disks", job, disks, 0, 30)

        has_draid = any(
            vdev["type"].startswith("DRAID")
            for vdev in data["topology"]["data"] + data["topology"].get("special", [])
        )
        properties = build_pool_properties(dedup_table_quota_value)
        filesystem_properties = build_fs_properties(name, data["deduplication"], data["checksum"], has_draid)

        await self.middleware.run_in_thread(os.makedirs, os.path.dirname(ZPOOL_CACHE_FILE), exist_ok=True)

        pool_id = z_pool_guid = None
        try:
            job.set_progress(90, "Creating ZFS Pool")
            z_pool_guid = await self.middleware.call("zpool.create_pool_impl", {
                "name": name,
                "vdevs": vdevs,
                "properties": properties,
                "filesystem_properties": filesystem_properties,
            })

            job.set_progress(95, "Setting pool options")

            # Inherit mountpoint after create because we set mountpoint on creation
            # making it a "local" source.
            await self.middleware.call(
                "pool.dataset.update_impl", UpdateImplArgs(name=name, iprops={"mountpoint"})
            )
            await self.middleware.call("zfs.resource.mount", name)

            pool_id = await self.middleware.call(
                "datastore.insert",
                "storage.volume",
                {"name": name, "guid": str(z_pool_guid), "all_sed": data["all_sed"]},
                {"prefix": "vol_"},
            )
            await self.middleware.call("datastore.insert", "storage.scrub", {"volume": pool_id}, {"prefix": "scrub_"})
        except Exception as e:
            # Something went wrong, roll back and destroy the pool.
            self.logger.debug("Pool %r failed to create with topology %r", name, data["topology"])
            if z_pool_guid:
                try:
                    await self.middleware.call("zfs.pool.delete", name)
                except Exception:
                    self.logger.warning("Failed to delete pool on zpool.create rollback", exc_info=True)
            if pool_id:
                await self.middleware.call("datastore.delete", "storage.volume", pool_id)
            if isinstance(e, ZpoolException):
                raise CallError(str(e), e.errno) from e
            raise

        # There is really no point in waiting for all these services to reload so do
        # them in the background.
        self.middleware.create_task(self.middleware.call("pool.restart_services"))

        pool = await self.middleware.call("pool.get_instance", pool_id)
        await self.middleware.call_hook("pool.post_create", pool=pool)
        await self.middleware.call_hook("pool.post_create_or_update", pool=pool)
        self.middleware.send_event("pool.query", "ADDED", id=pool_id, fields=pool)
        await self.middleware.call("zpool.send_change_event", name, "ADDED")
        return (await self.middleware.call(
            "zpool.query", {"pool_names": [name], "topology": True, "scan": True}
        ))[0]

    @private
    @pass_thread_local_storage
    def create_pool_impl(self, tls, data):
        """Create the ZFS pool via ``truenas_pylibzfs`` and return its GUID.

        This is the only step that touches the libzfs handle directly. ``data`` is
        a dict with keys: ``name``, ``vdevs`` (converted topology with populated
        ``/dev/<gptid>`` device lists), ``properties``, and ``filesystem_properties``.
        """
        kwargs = {
            "name": data["name"],
            **assemble_create_pool_vdev_kwargs(data["vdevs"]),
            "properties": data["properties"],
            "filesystem_properties": data["filesystem_properties"],
        }
        try:
            tls.lzh.create_pool(**kwargs)
        except ZFSException as e:
            raise ZpoolCreateException(data["name"], str(e)) from e

        return query_impl(tls.lzh, {"pool_names": [data["name"]]})[0]["guid"]
