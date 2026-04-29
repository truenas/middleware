import errno

from truenas_pylibzfs import ZFSError, ZFSException

from middlewared.api import api_method
from middlewared.api.current import (
    PoolAttachmentsArgs,
    PoolAttachmentsResult,
    PoolFilesystemChoicesArgs,
    PoolFilesystemChoicesResult,
    PoolGetDisksArgs,
    PoolGetDisksResult,
    PoolIsUpgradedArgs,
    PoolIsUpgradedResult,
    PoolProcessesArgs,
    PoolProcessesResult,
    ZFSResourceQuery,
)
from middlewared.plugins.zpool import get_zpool_disks_impl, get_zpool_features_impl
from middlewared.service import Service, ValidationError, private


class PoolService(Service):

    @private
    def find_disk_from_topology(self, label, pool, options=None):
        options = options or {}
        include_top_level_vdev = options.get("include_top_level_vdev", False)
        include_siblings = options.get("include_siblings", False)

        check = []
        found = None
        for root, children in pool["topology"].items():
            check.append((root, children))

        while check and not found:
            root, children = check.pop()
            for c in children:
                if c["type"] == "DISK":
                    if label in (c["path"].replace("/dev/", ""), c["guid"]):
                        found = (root, c)
                        break
                elif include_top_level_vdev and c["guid"] == label:
                    found = (root, c)
                    break

                if c["children"]:
                    check.append((root, c["children"]))

            if found is not None and include_siblings:
                found = (found[0], found[1], children)

        return found

    @api_method(PoolAttachmentsArgs, PoolAttachmentsResult, roles=["POOL_READ"])
    async def attachments(self, oid):
        """
        Return a list of services dependent of this pool.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.
        """
        pool = await self.middleware.call("pool.get_instance", oid)
        return await self.middleware.call("pool.dataset.attachments_with_path", pool["path"])

    @api_method(PoolProcessesArgs, PoolProcessesResult, roles=["POOL_READ"])
    async def processes(self, oid):
        """
        Returns a list of running processes using this pool.
        """
        pool = await self.middleware.call("pool.get_instance", oid)
        processes = []
        try:
            processes = await self.middleware.call("pool.dataset.processes", pool["name"])
        except ValidationError as e:
            if e.errno == errno.ENOENT:
                # Dataset might not exist (e.g. not online), this is not an error
                pass
            else:
                raise

        return processes

    @api_method(
        PoolGetDisksArgs,
        PoolGetDisksResult,
        pass_thread_local_storage=True,
        roles=["POOL_READ"]
    )
    def get_disks(self, tls, oid):
        """
        Return the device names of all disks belonging to a pool.

        Queries the database for the pool matching the given `id` and
        resolves each vdev, cache, log, special, dedup, and spare device
        to its whole-disk device name (e.g. sda, nvme0n1). If `id` is
        not provided, disks for all imported pools in the database are
        returned. Pools that are not currently imported are skipped.

        Raises a `ValidationError` if `id` is provided but does not
        match any pool in the database.
        """
        filters = list() if not oid else [["id", "=", oid]]
        pools = self.middleware.call_sync(
            "datastore.query", "storage.volume", filters
        )
        if not pools and oid:
            raise ValidationError(
                "pool.get_disks",
                f"pool with database id {oid!r} does not exist",
                errno.ENOENT
            )

        disks = list()
        for i in pools:
            try:
                disks.extend(get_zpool_disks_impl(tls.lzh, i["vol_name"]))
            except ZFSException as e:
                if e.code == ZFSError.EZFS_NOENT:
                    continue
                raise
        return disks

    @api_method(PoolFilesystemChoicesArgs, PoolFilesystemChoicesResult, roles=["DATASET_READ"])
    async def filesystem_choices(self, types):
        """Returns all available zfs resources based on `types`."""
        info = []
        for i in await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(get_children=True, properties=None)
        ):
            if i["type"] in types:
                info.append(i["name"])
        return info

    @api_method(
        PoolIsUpgradedArgs,
        PoolIsUpgradedResult,
        pass_thread_local_storage=True,
        roles=["POOL_READ"]
    )
    def is_upgraded(self, tls, oid):
        """
        Returns whether or not the pool of `id` is on the latest version
        and with all feature flags enabled.

        Queries the database for the pool matching the given `id`, then
        checks each ZFS feature flag on the pool. Returns `true` only
        when every feature flag is in the ENABLED or ACTIVE state.
        Returns `false` if the pool is not currently imported or if
        the feature flags cannot be read for any reason.

        Raises a `ValidationError` if `id` does not match any pool in
        the database.
        """
        pool = self.middleware.call_sync(
            "datastore.query", "storage.volume", [["id", "=", oid]]
        )
        if not pool:
            raise ValidationError(
                "pool.is_upgraded",
                f"pool with database id {oid!r} does not exist",
                errno.ENOENT
            )

        pname = pool[0]["vol_name"]
        try:
            for feat, info in get_zpool_features_impl(tls.lzh, pname).items():
                if info.state not in ("ENABLED", "ACTIVE"):
                    return False
        except Exception:
            return False
        return True
