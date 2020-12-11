import logging

import bidict

from middlewared.service import private, Service
from middlewared.service_exception import MatchNotFound
from middlewared.utils import osc

logger = logging.getLogger(__name__)


class DiskService(Service):
    @private
    async def disk_by_zfs_guid(self, guid):
        try:
            return await self.middleware.call(
                "disk.query", [["zfs_guid", "=", guid]], {"extra": {"include_expired": True}, "get": True},
            )
        except MatchNotFound:
            return None

    @private
    async def sync_zfs_guid(self, pool_id_or_pool):
        if isinstance(pool_id_or_pool, dict):
            topology = pool_id_or_pool["topology"]
        elif isinstance(pool_id_or_pool, str):
            pool = await self.middleware.call("zfs.pool.query", [["name", "=", pool_id_or_pool]], {"get": True})
            topology = await self.middleware.call("pool.transform_topology", pool["groups"])
        else:
            pool = await self.middleware.call("pool.get_instance", pool_id_or_pool)
            topology = pool["topology"]

        if topology is None:
            return

        disk_to_guid = bidict.bidict()
        for vdev in await self.middleware.call("pool.flatten_topology", topology):
            if vdev["type"] == "DISK" and vdev["disk"] is not None:
                disk_to_guid[vdev["disk"]] = vdev["guid"]

        for disk in await self.middleware.call("disk.query", [], {"extra": {"include_expired": True}}):
            guid = disk_to_guid.get(disk["devname"])
            if guid is not None and guid != disk["zfs_guid"]:
                logger.debug("Setting disk %r zfs_guid %r", disk["identifier"], guid)
                await self.middleware.call(
                    "datastore.update", "storage.disk", disk["identifier"], {"zfs_guid": guid}, {"prefix": "disk_"},
                )
            elif disk["zfs_guid"]:
                devname = disk_to_guid.inv.get(disk["zfs_guid"])
                if devname is not None and devname != disk["devname"]:
                    logger.debug("Removing disk %r zfs_guid as %r has it", disk["identifier"], devname)
                    await self.middleware.call(
                        "datastore.update", "storage.disk", disk["identifier"], {"zfs_guid": None}, {"prefix": "disk_"},
                    )


async def devd_zfs_hook(middleware, data):
    if data.get("type") in (
        "sysevent.fs.zfs.config_sync",
    ):
        try:
            await middleware.call("disk.sync_zfs_guid", data["pool"])
        except MatchNotFound:
            pass


async def zfs_events_hook(middleware, data):
    event_id = data["class"]

    if event_id in [
        "sysevent.fs.zfs.config_sync",
    ]:
        try:
            await middleware.call("disk.sync_zfs_guid", data["pool"])
        except MatchNotFound:
            pass


async def hook(middleware, pool):
    await middleware.call("disk.sync_zfs_guid", pool)


async def setup(middleware):
    if osc.IS_FREEBSD:
        middleware.register_hook("devd.zfs", devd_zfs_hook)
    else:
        middleware.register_hook("zfs.pool.events", zfs_events_hook)

    middleware.register_hook("pool.post_create_or_update", hook)
