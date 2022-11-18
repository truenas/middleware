import asyncio
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

        if not (found := await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)):
            verrors.add('options.label', f'Label {options["label"]} not found.', errno.ENOENT)

        verrors.check()

        swap_disks = [disk['devname']]
        if found[1] and await self.middleware.run_in_thread(os.path.exists, found[1]['path']):
            if from_disk := await self.middleware.call('disk.label_to_disk', found[1]['path'].replace('/dev/', '')):
                # If the disk we are replacing is still available, remove it from swap as well
                swap_disks.append(from_disk)

        await self.middleware.call('disk.swaps_remove_disks', swap_disks)

        vdev = []
        format_opts = {disk['devname']: {'vdev': vdev, 'create_swap': found[0] in ('data', 'spare')}}
        await self.middleware.call('pool.format_disks', job, format_opts)

        try:
            job.set_progress(30, 'Replacing disk')
            new_devname = vdev[0].replace('/dev/', '')
            await self.middleware.call('zfs.pool.replace', pool['name'], options['label'], new_devname)
            try:
                vdev = await self.middleware.call('zfs.pool.get_vdev', pool['name'], options['label'])
                if vdev['status'] not in ('ONLINE', 'DEGRADED'):
                    job.set_progress(80, 'Detaching old disk')
                    # If we are replacing a faulted disk, kick it right after replace is initiated.
                    await self.middleware.call('zfs.pool.detach', pool['name'], options['label'])
            except Exception:
                self.logger.warning('Failed to detach device with label %r', options['label'], exc_info=True)
        finally:
            # Needs to happen even if replace failed to put back disk that had been
            # removed from swap prior to replacement
            asyncio.ensure_future(self.middleware.call('disk.swaps_configure'))

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
