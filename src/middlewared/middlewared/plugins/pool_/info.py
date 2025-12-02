import errno

from middlewared.api import api_method
from middlewared.api.current import (
    PoolGetDisksArgs, PoolGetDisksResult, PoolFilesystemChoicesArgs, PoolFilesystemChoicesResult, PoolIsUpgradedArgs,
    PoolIsUpgradedResult, PoolAttachmentsArgs, PoolAttachmentsResult, PoolProcessesArgs, PoolProcessesResult
)
from middlewared.service import CallError, private, Service, ValidationError


class PoolService(Service):

    @private
    def find_disk_from_topology(self, label, pool, options=None):
        options = options or {}
        include_top_level_vdev = options.get('include_top_level_vdev', False)
        include_siblings = options.get('include_siblings', False)

        check = []
        found = None
        for root, children in pool['topology'].items():
            check.append((root, children))

        while check and not found:
            root, children = check.pop()
            for c in children:
                if c['type'] == 'DISK':
                    if label in (c['path'].replace('/dev/', ''), c['guid']):
                        found = (root, c)
                        break
                elif include_top_level_vdev and c['guid'] == label:
                    found = (root, c)
                    break

                if c['children']:
                    check.append((root, c['children']))

            if found is not None and include_siblings:
                found = (found[0], found[1], children)

        return found

    @api_method(PoolAttachmentsArgs, PoolAttachmentsResult, roles=['POOL_READ'])
    async def attachments(self, oid):
        """
        Return a list of services dependent of this pool.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        return await self.middleware.call('pool.dataset.attachments_with_path', pool['path'])

    @api_method(PoolProcessesArgs, PoolProcessesResult, roles=['POOL_READ'])
    async def processes(self, oid):
        """
        Returns a list of running processes using this pool.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        processes = []
        try:
            processes = await self.middleware.call('pool.dataset.processes', pool['name'])
        except ValidationError as e:
            if e.errno == errno.ENOENT:
                # Dataset might not exist (e.g. not online), this is not an error
                pass
            else:
                raise

        return processes

    @api_method(PoolGetDisksArgs, PoolGetDisksResult, roles=['POOL_READ'])
    async def get_disks(self, oid):
        """
        Get all disks in use by pools.
        If `id` is provided only the disks from the given pool `id` will be returned.
        """
        disks = []
        for pool in await self.middleware.call('pool.query', [] if not oid else [('id', '=', oid)]):
            if pool['status'] != 'OFFLINE':
                disks.extend(await self.middleware.call('zfs.pool.get_disks', pool['name']))
        return disks

    @api_method(PoolFilesystemChoicesArgs, PoolFilesystemChoicesResult, roles=['DATASET_READ'])
    async def filesystem_choices(self, types):
        """Returns all available zfs resources based on `types`."""
        info = []
        for i in await self.middleware.call(
            'zfs.resource.query_impl',
            {'get_children': True, 'properties': None}
        ):
            if i['type'] in types:
                info.append(i['name'])
        return info

    @api_method(PoolIsUpgradedArgs, PoolIsUpgradedResult, roles=['POOL_READ'])
    async def is_upgraded(self, oid):
        """
        Returns whether or not the pool of `id` is on the latest version and with all feature
        flags enabled.

        .. examples(websocket)::

          Check if pool of id 1 is upgraded.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.is_upgraded",
                "params": [1]
            }
        """
        return await self.is_upgraded_by_name((await self.middleware.call('pool.get_instance', oid))['name'])

    @private
    async def is_upgraded_by_name(self, name):
        try:
            return await self.middleware.call('zfs.pool.is_upgraded', name)
        except CallError:
            return False
