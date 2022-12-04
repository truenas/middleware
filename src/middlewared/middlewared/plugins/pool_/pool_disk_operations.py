from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import CallError, item_method, job, Service, ValidationErrors


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns(Bool('detached'))
    async def detach(self, oid, options):
        """
        Detach a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        .. examples(websocket)::

          Detach ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.detach,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)

        verrors = ValidationErrors()
        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        verrors.check()

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            await self.middleware.call('disk.swaps_remove_disks', [disk])

        await self.middleware.call('zfs.pool.detach', pool['name'], found[1]['guid'])

        if disk:
            wipe_job = await self.middleware.call('disk.wipe', disk, 'QUICK')
            await wipe_job.wait()
            if wipe_job.error:
                raise CallError(f'Failed to wipe disk {disk}: {wipe_job.error}')

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns(Bool('offline_successful'))
    async def offline(self, oid, options):
        """
        Offline a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        .. examples(websocket)::

          Offline ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.offline,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)

        verrors = ValidationErrors()
        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        verrors.check()

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            await self.middleware.call('disk.swaps_remove_disks', [disk])

        await self.middleware.call('zfs.pool.offline', pool['name'], found[1]['guid'])

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns(Bool('online_successful'))
    async def online(self, oid, options):
        """
        Online a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        .. examples(websocket)::

          Online ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.online,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)

        verrors = ValidationErrors()

        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        verrors.check()

        await self.middleware.call('zfs.pool.online', pool['name'], found[1]['guid'])

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            self.middleware.create_task(self.middleware.call('disk.swaps_configure'))

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns()
    @job(lock=lambda args: f'{args[0]}_remove')
    async def remove(self, job, oid, options):
        """
        Remove a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        Error codes:

            EZFS_NOSPC(2032): out of space to remove a device
            EZFS_NODEVICE(2017): no such device in pool
            EZFS_NOREPLICAS(2019): no valid replicas

        .. examples(websocket)::

          Remove ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.remove,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)

        verrors = ValidationErrors()

        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool, True)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')

        verrors.check()

        job.set_progress(20, f'Initiating removal of {options["label"]!r} ZFS device')
        await self.middleware.call('zfs.pool.remove', pool['name'], found[1]['guid'])
        job.set_progress(40, 'Waiting for removal of ZFS device to complete')
        # We would like to wait not for the removal to actually complete for cases where the removal might not
        # be synchronous like removing top level vdevs except for slog and l2arc
        await self.middleware.call('zfs.pool.wait', pool['name'], {'activity_type': 'REMOVE'})
        job.set_progress(60, 'Removal of ZFS device complete')

        if found[1]['type'] != 'DISK':
            disk_paths = [d['path'] for d in found[1]['children']]
        else:
            disk_paths = [found[1]['path']]

        wipe_jobs = []
        for disk_path in disk_paths:
            disk = await self.middleware.call(
                'disk.label_to_disk', disk_path.replace('/dev/', '')
            )
            if disk:
                wipe_job = await self.middleware.call('disk.wipe', disk, 'QUICK', False)
                wipe_jobs.append((disk, wipe_job))

        job.set_progress(70, 'Wiping disks')
        error_str = ''
        for index, item in enumerate(wipe_jobs):
            disk, wipe_job = item
            await wipe_job.wait()
            if wipe_job.error:
                error_str += f'{index + 1}) {disk}: {wipe_job.error}\n'

        if error_str:
            raise CallError(f'Failed to wipe disks:\n{error_str}')

        job.set_progress(100, 'Successfully completed wiping disks')
