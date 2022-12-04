import asyncio
import errno
import os

from middlewared.schema import accepts, Bool, Dict, Int, returns
from middlewared.service import CallError, item_method, job, Service, ValidationError
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @item_method
    @accepts(
        Int('id'),
        Dict(
            'options',
            Bool('cascade', default=False),
            Bool('restart_services', default=False),
            Bool('destroy', default=False),
        ),
    )
    @returns()
    @job(lock='pool_export')
    async def export(self, job, oid, options):
        """
        Export pool of `id`.

        `cascade` will delete all attachments of the given pool (`pool.attachments`).
        `restart_services` will restart services that have open files on given pool.
        `destroy` will also PERMANENTLY destroy the pool/data.

        .. examples(websocket)::

          Export pool of id 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.export,
                "params": [1, {
                    "cascade": true,
                    "destroy": false
                }]
            }

        If this is an HA system and failover is enabled and the last zpool is
        exported/disconnected, then this will raise EOPNOTSUPP. Failover must
        be disabled before exporting the last zpool on the system.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        root_ds = await self.middleware.call('pool.dataset.query', [['id', '=', pool['name']]])
        if root_ds and root_ds[0]['locked'] and os.path.exists(root_ds[0]['mountpoint']):
            # We should be removing immutable flag in this case if the path exists
            await self.middleware.call('filesystem.set_immutable', False, root_ds[0]['mountpoint'])

        pool_count = await self.middleware.call('pool.query', [], {'count': True})
        if pool_count == 1 and await self.middleware.call('failover.licensed'):
            if not (await self.middleware.call('failover.config'))['disabled']:
                err = errno.EOPNOTSUPP
                raise CallError('Disable failover before exporting last pool on system.', err)

        enable_on_import_key = f'pool:{pool["name"]}:enable_on_import'
        enable_on_import = {}
        if not options['cascade']:
            if await self.middleware.call('keyvalue.has_key', enable_on_import_key):
                enable_on_import = await self.middleware.call('keyvalue.get', enable_on_import_key)

        for i, delegate in enumerate(await self.middleware.call('pool.dataset.get_attachment_delegates')):
            job.set_progress(
                i, f'{"Deleting" if options["cascade"] else "Disabling"} pool attachments: {delegate.title}')

            attachments = await delegate.query(pool['path'], True)
            if attachments:
                if options["cascade"]:
                    await delegate.delete(attachments)
                else:
                    await delegate.toggle(attachments, False)
                    enable_on_import[delegate.name] = list(
                        set(enable_on_import.get(delegate.name, [])) |
                        {attachment['id'] for attachment in attachments}
                    )

        if enable_on_import:
            await self.middleware.call('keyvalue.set', enable_on_import_key, enable_on_import)
        else:
            await self.middleware.call('keyvalue.delete', enable_on_import_key)

        job.set_progress(20, 'Terminating processes that are using this pool')
        try:
            await self.middleware.call('pool.dataset.kill_processes', pool['name'],
                                       options.get('restart_services', False))
        except ValidationError as e:
            if e.errno == errno.ENOENT:
                # Dataset might not exist (e.g. pool is not decrypted), this is not an error
                pass
            else:
                raise

        await self.middleware.call('iscsi.global.terminate_luns_for_pool', pool['name'])

        job.set_progress(30, 'Removing pool disks from swap')
        disks = await self.middleware.call('pool.get_disks', oid)

        # We don't want to configure swap immediately after removing those disks because we might get in a race
        # condition where swap starts using the pool disks as the pool might not have been exported/destroyed yet
        await self.middleware.call('disk.swaps_remove_disks', disks, {'configure_swap': False})

        await self.middleware.call_hook('pool.pre_export', pool=pool['name'], options=options, job=job)

        if pool['status'] == 'OFFLINE':
            # Pool exists only in database, its not imported
            pass
        elif options['destroy']:
            job.set_progress(60, 'Destroying pool')
            await self.middleware.call('zfs.pool.delete', pool['name'])

            job.set_progress(80, 'Cleaning disks')

            async def unlabel(disk):
                wipe_job = await self.middleware.call(
                    'disk.wipe', disk, 'QUICK', False, {'configure_swap': False}
                )
                await wipe_job.wait()
                if wipe_job.error:
                    self.logger.warning(f'Failed to wipe disk {disk}: {wipe_job.error}')

            await asyncio_map(unlabel, disks, limit=16)

            await self.middleware.call('disk.sync_all')

            if pool['encrypt'] > 0:
                try:
                    os.remove(pool['encryptkey_path'])
                except OSError as e:
                    self.logger.warning(
                        'Failed to remove encryption key %s: %s',
                        pool['encryptkey_path'],
                        e,
                        exc_info=True,
                    )
        else:
            job.set_progress(80, 'Exporting pool')
            await self.middleware.call('zfs.pool.export', pool['name'])

        job.set_progress(90, 'Cleaning up')
        if os.path.isdir(pool['path']):
            try:
                # We dont try to remove recursively to avoid removing files that were
                # potentially hidden by the mount
                os.rmdir(pool['path'])
            except OSError as e:
                self.logger.warning('Failed to remove mountpoint %s: %s', pool['path'], e)

        await self.middleware.call('datastore.delete', 'storage.volume', oid)
        await self.middleware.call(
            'pool.dataset.delete_encrypted_datasets_from_db',
            [['OR', [['name', '=', pool['name']], ['name', '^', f'{pool["name"]}/']]]],
        )
        await self.middleware.call_hook('dataset.post_delete', pool['name'])

        # scrub needs to be regenerated in crontab
        await self.middleware.call('service.restart', 'cron')

        # Let's reconfigure swap in case dumpdev needs to be configured again
        self.middleware.create_task(self.middleware.call('disk.swaps_configure'))

        await self.middleware.call_hook('pool.post_export', pool=pool['name'], options=options)
        self.middleware.send_event('pool.query', 'CHANGED', id=oid, cleared=True)
        self.middleware.send_event('pool.query', 'REMOVED', id=oid)
