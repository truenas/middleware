import errno

from middlewared.schema import accepts, Bool, Dict, Int, List, returns, Str
from middlewared.service import CallError, item_method, private, Service, ValidationError


class PoolService(Service):

    @private
    def find_disk_from_topology(self, label, pool, include_top_level_vdev=False):
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
        return found

    @item_method
    @accepts(Int('id'))
    @returns(List(items=[Dict(
        'attachment',
        Str('type', required=True),
        Str('service', required=True, null=True),
        List('attachments', items=[Str('attachment_name')]),
    )], register=True))
    async def attachments(self, oid):
        """
        Return a list of services dependent of this pool.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        return await self.middleware.call('pool.dataset.attachments_with_path', pool['path'])

    @item_method
    @accepts(Int('id'))
    @returns(List(items=[Dict(
        'process',
        Int('pid', required=True),
        Str('name', required=True),
        Str('service'),
        Str('cmdline', max_length=None),
    )], register=True))
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

    @item_method
    @accepts(Int('id', required=False, default=None, null=True))
    @returns(List('pool_disks', items=[Str('disk')]))
    async def get_disks(self, oid):
        """
        Get all disks in use by pools.
        If `id` is provided only the disks from the given pool `id` will be returned.
        """
        disks = []
        for pool in await self.middleware.call('pool.query', [] if not oid else [('id', '=', oid)]):
            if pool['is_decrypted'] and pool['status'] != 'OFFLINE':
                disks.extend(await self.middleware.call('zfs.pool.get_disks', pool['name']))
        return disks

    @accepts(List('types', items=[Str('type', enum=['FILESYSTEM', 'VOLUME'])], default=['FILESYSTEM', 'VOLUME']))
    @returns(List(items=[Str('filesystem_name')]))
    async def filesystem_choices(self, types):
        """
        Returns all available datasets, except the following:
            1. system datasets
            2. glusterfs datasets
            3. application(s) internal datasets

        .. examples(websocket)::

          Get all datasets.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.filesystem_choices",
                "params": []
            }

          Get only filesystems (exclude volumes).

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.filesystem_choices",
                "params": [["FILESYSTEM"]]
            }
        """
        vol_names = [vol['name'] for vol in await self.middleware.call('pool.query')]
        return [
            y['name'] for y in await self.middleware.call(
                'zfs.dataset.query',
                [
                    ('pool', 'in', vol_names),
                    ('type', 'in', types),
                ] + await self.middleware.call('pool.dataset.internal_datasets_filters'),
                {'extra': {'retrieve_properties': False}, 'order_by': ['name']},
            )
        ]

    @accepts(Int('id', required=True))
    @returns(Bool('pool_is_upgraded'))
    @item_method
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
