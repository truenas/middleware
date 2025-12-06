from middlewared.service import private, Service
from middlewared.service_exception import MatchNotFound


class DiskService(Service):
    @private
    async def disk_by_zfs_guid(self, guid):
        """
        This method returns a single disk entry with the specified
        ZFS guid. The database however may contain multiple disks
        with the same GUID differentiated by the `expiretime` key.

        The `expiretime` key has the following special meaning depending
        on value type:
        `None` - disk is currently detected and in the system
        `datetime` - disk was removed and will expire at the specified
        time.

        Since type is inconsistent for this value, it cannot be used
        for ordering disks using builtin sorted() method in filter_list.
        """
        disk = None

        disks_with_zfs_guid = await self.middleware.call(
            "disk.query",
            [["zfs_guid", "=", guid]],
            {"extra": {"include_expired": True}},
        )

        for entry in disks_with_zfs_guid:
            if entry['expiretime'] is None:
                disk = entry
                break

            if disk is None:
                disk = entry
            elif entry['expiretime'] > disk['expiretime']:
                disk = entry

        return disk

    @private
    async def sync_all_zfs_guid(self):
        for pool in await self.middleware.call(
            "zfs.pool.query",
            [["name", "!=", await self.middleware.call("boot.pool_name")]],
        ):
            try:
                await self.sync_zfs_guid({
                    **pool,
                    "topology": await self.middleware.call("pool.transform_topology", pool["groups"])
                })
            except Exception:
                self.logger.error("Error running sync_zfs_guid for pool %r", pool["name"])

    @private
    async def sync_zfs_guid(self, pool_id_or_pool):
        if isinstance(pool_id_or_pool, dict):
            pool = pool_id_or_pool
            topology = pool_id_or_pool["topology"]
        elif isinstance(pool_id_or_pool, str):
            pool = await self.middleware.call("zfs.pool.query", [["name", "=", pool_id_or_pool]], {"get": True})
            topology = await self.middleware.call("pool.transform_topology", pool["groups"])
        else:
            pool = await self.middleware.call("pool.get_instance", pool_id_or_pool)
            topology = pool["topology"]

        if topology is None:
            return

        disk_to_guid, guid_to_disk = dict(), dict()
        for vdev in await self.middleware.call("pool.flatten_topology", topology):
            if vdev["type"] == "DISK":
                if vdev["disk"] is not None:
                    disk_to_guid[vdev["disk"]] = vdev["guid"]
                    guid_to_disk[vdev["guid"]] = vdev["disk"]
                else:
                    self.logger.debug("Pool %r vdev %r disk is None", pool["name"], vdev["guid"])

        events = set()
        for disk in await self.middleware.call("disk.query", [], {"extra": {"include_expired": True}}):
            guid = disk_to_guid.get(disk["devname"])
            if guid is not None and guid != disk["zfs_guid"]:
                if not disk["expiretime"]:
                    self.logger.debug(
                        "Setting disk %r (%r) zfs_guid %r",
                        disk["identifier"], disk["devname"], guid,
                    )
                    events.add(disk["identifier"])
                    await self.middleware.call(
                        "datastore.update", "storage.disk", disk["identifier"],
                        {"zfs_guid": guid}, {"prefix": "disk_", "send_events": False},
                    )
            elif disk["zfs_guid"]:
                devname = guid_to_disk.get(disk["zfs_guid"])
                if devname is not None and devname != disk["devname"]:
                    self.logger.debug(
                        "Removing disk %r (%r) zfs_guid %r as %r has it",
                        disk["identifier"], disk["devname"], disk["zfs_guid"], devname,
                    )
                    events.add(disk["identifier"])
                    await self.middleware.call(
                        "datastore.update", "storage.disk", disk["identifier"],
                        {"zfs_guid": None}, {"prefix": "disk_", "send_events": False},
                    )

        if events:
            disks = {i["identifier"]: i for i in await self.middleware.call("disk.query")}
            for event in events:
                if event in disks:
                    self.middleware.send_event("disk.query", "CHANGED", id=event, fields=disks[event])


async def zfs_events_hook(middleware, data):
    if data["class"] == "sysevent.fs.zfs.config_sync":
        try:
            await middleware.call("disk.sync_zfs_guid", data["pool"])
        except MatchNotFound:
            pass

        # We do this separately and do not get it from above because right now above implementation would handle
        # this for disks which are not in a pool which is in our database
        # Ideally would be better to get this once and reuse it for above too
        if await middleware.call('system.sed_enabled') and (
            pool := await middleware.call("pool.query", [["name", "=", data["pool"]]], {'force_sql_filters': True})
        ):
            if pool["healthy"]:
                # Let's only trigger this if pool is healthy
                middleware.create_task(middleware.call("pool.update_all_sed_attr", True, data["pool"]))


async def hook(middleware, pool):
    await middleware.call("disk.sync_zfs_guid", pool)


async def setup(middleware):
    middleware.register_hook("zfs.pool.events", zfs_events_hook)
    middleware.register_hook("pool.post_create_or_update", hook)
