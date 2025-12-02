import asyncio
import errno
import itertools

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDetachArgs, PoolDetachResult, PoolOfflineArgs, PoolOfflineResult,
    PoolOnlineArgs, PoolOnlineResult, PoolRemoveArgs, PoolRemoveResult
)
from middlewared.service import CallError, job, Service, ValidationErrors


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @api_method(
        PoolDetachArgs,
        PoolDetachResult,
        audit='Disk detach',
        audit_callback=True,
        roles=['POOL_WRITE']
    )
    async def detach(self, audit_callback, oid, options):
        """
        Detach a disk from pool of id `id`.

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

        if found[1]['type'] != 'DISK':
            disk_paths = [d['path'] for d in found[1]['children']]
        else:
            disk_paths = [found[1]['path']]
        audit_callback(f'{", ".join(disk_paths)} from {pool["name"]!r} pool')

        await self.middleware.call('zfs.pool.detach', pool['name'], found[1]['guid'])

        if disk and options['wipe']:
            wipe_job = await self.middleware.call('disk.wipe', disk, 'QUICK')
            await wipe_job.wait()
            if wipe_job.error:
                raise CallError(f'Failed to wipe disk {disk}: {wipe_job.error}')

        return True

    @api_method(
        PoolOfflineArgs,
        PoolOfflineResult,
        audit='Disk offline',
        audit_callback=True,
        roles=['POOL_WRITE']
    )
    async def offline(self, audit_callback, oid, options):
        """
        Offline a disk from pool of id `id`.

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

        if found[1]['type'] != 'DISK':
            disk_paths = [d['path'] for d in found[1]['children']]
        else:
            disk_paths = [found[1]['path']]
        audit_callback(f'{", ".join(disk_paths)} in {pool["name"]!r} pool')

        await self.middleware.call('zfs.pool.offline', pool['name'], found[1]['guid'])

        return True

    @api_method(
        PoolOnlineArgs,
        PoolOnlineResult,
        audit='Disk online',
        audit_callback=True,
        roles=['POOL_WRITE']
    )
    async def online(self, audit_callback, oid, options):
        """
        Online a disk from pool of id `id`.

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

        if found[1]['type'] != 'DISK':
            disk_paths = [d['path'] for d in found[1]['children']]
        else:
            disk_paths = [found[1]['path']]
        audit_callback(f'{", ".join(disk_paths)} in {pool["name"]!r} pool')

        await self.middleware.call('zfs.pool.online', pool['name'], found[1]['guid'])

        return True

    @api_method(
        PoolRemoveArgs,
        PoolRemoveResult,
        audit='Disk remove',
        audit_callback=True,
        roles=['POOL_WRITE']
    )
    @job(lock=lambda args: f'{args[0]}_remove')
    async def remove(self, job, audit_callback, oid, options):
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

        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool, {
            'include_top_level_vdev': True,
        })
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')

        verrors.check()

        job.set_progress(20, f'Initiating removal of {options["label"]!r} ZFS device')
        await self.middleware.call('zfs.pool.remove', pool['name'], found[1]['guid'])
        job.set_progress(40, 'Waiting for removal of ZFS device to complete')
        # We would like to wait for the removal to actually complete for cases where the removal might not
        # be synchronous like removing top level vdevs except for slog and l2arc
        await self.middleware.call('zfs.pool.wait', pool['name'], {'activity_type': 'REMOVE'})
        job.set_progress(60, 'Removal of ZFS device complete')

        if found[1]['type'] != 'DISK':
            disk_paths = [d['path'] for d in found[1]['children']]
        else:
            disk_paths = [found[1]['path']]
        audit_callback(f'{", ".join(disk_paths)} from {pool["name"]!r} pool')

        job.set_progress(70, 'Wiping disks')
        disks_to_wipe = set()
        for disk_path in disk_paths:
            disk = await self.middleware.call(
                'disk.label_to_disk', disk_path.replace('/dev/', '')
            )
            if disk:
                disks_to_wipe.add(disk)

        max_retries = 30
        disks_errors = {}
        for retry in itertools.count(1):
            wipe_jobs = []
            for disk in disks_to_wipe:
                wipe_job = await self.middleware.call('disk.wipe', disk, 'QUICK', False)
                wipe_jobs.append((disk, wipe_job))

            disks_errors = {}
            for disk, wipe_job in wipe_jobs:
                try:
                    await wipe_job.wait(raise_error=True, raise_error_forward_classes=(OSError,))
                except OSError as e:
                    if not (e.errno == errno.EBUSY and retry < max_retries):
                        # Sometimes we get this error even after `zfs.pool.wait` confirms the successful device removal
                        raise
                except Exception as e:
                    disks_errors[disk] = str(e)
                    disks_to_wipe.remove(disk)
                else:
                    disks_to_wipe.remove(disk)

            if not disks_to_wipe or disks_errors:
                break

            await asyncio.sleep(1)

        if disks_errors:
            disks_errors = '\n'.join(sorted({f'{disk}: {error}' for disk, error in disks_errors.items()}))
            raise CallError(f'Failed to wipe disks:\n{disks_errors}')

        job.set_progress(100, 'Successfully completed wiping disks')
