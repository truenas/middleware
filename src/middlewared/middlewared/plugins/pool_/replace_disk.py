import errno

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import item_method, job, Service, ValidationErrors
from middlewared.service_exception import MatchNotFound


def find_disk_from_identifier(disks, ident):
    for v in disks.values():
        for info in filter(lambda x: x['identifier'] == ident, v):
            return info


class PoolService(Service):

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
        Str('disk', required=True),
        Bool('force', default=False),
        Bool('preserve_settings', default=True),
    ))
    @returns(Bool('replaced_successfully'))
    @job(lock='pool_replace')
    async def replace(self, job, oid, options):
        """
        Replace a disk on a pool.

        `label` is the ZFS guid or a device name
        `disk` is the identifier of a disk
        If `preserve_settings` is true, then settings (power management, S.M.A.R.T., etc.) of a disk being replaced
        will be applied to a new disk.

        .. examples(websocket)::

          Replace missing ZFS device with disk {serial}FOO.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.replace",
                "params": [1, {
                    "label": "80802394992848654",
                    "disk": "{serial}FOO"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        verrors = ValidationErrors()
        disk = find_disk_from_identifier(await self.middleware.call('disk.details'), options['disk'])
        if disk is None:
            verrors.add('options.disk', f'Disk {options["disk"]!r} not found.', errno.ENOENT)
        verrors.check()

        if disk['imported_zpool'] is not None:
            verrors.add(
                'options.disk',
                f'Disk {options["disk"]!r} is in use by zpool {disk["imported_zpool"]!r}.',
                errno.EBUSY
            )
        elif not options['force']:
            msg = ' Force must be specified.'
            if disk['exported_zpool'] is not None:
                verrors.add(
                    'options.force',
                    f'Disk {options["disk"]!r} is associated to exported zpool {disk["exported_zpool"]!r}.{msg}'
                )
            elif not await self.middleware.call('disk.check_clean', disk['devname']):
                verrors.add(
                    'options.force',
                    f'Disk {options["disk"]!r} is not clean, partitions were found.{msg}'
                )

        if not await self.middleware.call(
            'pool.find_disk_from_topology', options['label'], pool, {'include_siblings': True}
        ):
            verrors.add('options.label', f'Label {options["label"]} not found.', errno.ENOENT)

        verrors.check()

        vdev = []
        await self.middleware.call('pool.format_disks', job, {
            disk['devname']: {
                'vdev': vdev,
                'size': None,  # pool.format_disks checks size of disk
            },
        }, 0, 25)

        try:
            job.set_progress(30, 'Replacing disk')
            new_devname = vdev[0].replace('/dev/', '')
            await self.middleware.call('zfs.pool.replace', pool['name'], options['label'], new_devname)
        except Exception:
            raise

        if options['preserve_settings']:
            filters = [['zfs_guid', '=', options['label']]]
            options = {'extra': {'include_expired': True}, 'get': True}
            try:
                old_disk = await self.middleware.call('disk.query', filters, options)
                job.set_progress(98, 'Copying old disk settings to new')
                await self.middleware.call('disk.copy_settings', old_disk, disk)
            except MatchNotFound:
                pass

        return True
