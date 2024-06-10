import errno
import os

from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import item_method, job, Service, ValidationErrors
from middlewared.service_exception import MatchNotFound


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
        unused_disks = await self.middleware.call('disk.get_unused')
        if not (disk := list(filter(lambda x: x['identifier'] == options['disk'], unused_disks))):
            verrors.add('options.disk', 'Disk not found.', errno.ENOENT)
        else:
            disk = disk[0]
            if not options['force'] and not await self.middleware.call('disk.check_clean', disk['devname']):
                verrors.add('options.force', 'Disk is not clean, partitions were found.')

        if not (found := await self.middleware.call('pool.find_disk_from_topology', options['label'], pool, {
            'include_siblings': True,
        })):
            verrors.add('options.label', f'Label {options["label"]} not found.', errno.ENOENT)

        verrors.check()

        swap_disks = [disk['devname']]
        from_disk = None
        if found[1] and await self.middleware.run_in_thread(os.path.exists, found[1]['path']):
            if from_disk := await self.middleware.call('disk.label_to_disk', found[1]['path'].replace('/dev/', '')):
                # If the disk we are replacing is still available, remove it from swap as well
                swap_disks.append(from_disk)

        vdev = []
        await self.middleware.call('pool.format_disks', job, {
            disk['devname']: {
                'vdev': vdev,
                'size': None,  # pool.format_disks checks size of disk
            },
        })

        try:
            job.set_progress(30, 'Replacing disk')
            new_devname = vdev[0].replace('/dev/', '')
            await self.middleware.call('zfs.pool.replace', pool['name'], options['label'], new_devname)
        except Exception:
            raise
        else:
            if from_disk:
                await self.middleware.call('disk.wipe', from_disk, 'QUICK')

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
