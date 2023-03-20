import errno
import os
import shutil

from middlewared.schema import accepts, Bool, Dict, Int, returns
from middlewared.service import CallError, item_method, job, private, Service, ValidationError
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @private
    def cleanup_after_export(self, poolinfo, opts):
        if poolinfo['encrypt'] > 0:
            try:
                # this is CORE GELI encryption which doesn't exist on SCALE
                # so it means someone upgraded from CORE to SCALE and their
                # db has an entry with a GELI based encrypted pool in it so
                # we'll remove the GELI key files associated with the zpool
                os.remove(poolinfo['encryptkey'])
            except Exception:
                # not fatal, and doesn't really matter since SCALE can't
                # use this zpool anyways
                pass

        try:
            if all((opts['destroy'], opts['cascade'])) and (contents := os.listdir(poolinfo['path'])):
                if len(contents) == 1 and contents[0] == 'ix-applications':
                    # This means:
                    #   1. zpool was destroyed (disks were wiped)
                    #   2. end-user chose to delete all share configuration associated
                    #       to said zpool
                    #   3. somehow ix-applications was the only top-level directory that
                    #       got left behind
                    #
                    # Since all 3 above are true, then we just need to remove this directory
                    # so we don't leave dangling directory(ies) in /mnt.
                    # (i.e. it'll leave something like /mnt/tank/ix-application/blah)
                    shutil.rmtree(poolinfo['path'])
            else:
                # remove top-level directory for zpool (i.e. /mnt/tank (ONLY if it's empty))
                os.rmdir(poolinfo['path'])
        except FileNotFoundError:
            # means the pool was exported and the path where the
            # root dataset (zpool) was mounted was removed
            return
        except Exception:
            self.logger.warning('Failed to remove remaining directories after export', exc_info=True)

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
                raise CallError('Disable failover before exporting last pool on system.', errno.EOPNOTSUPP)

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

            async def unlabel(disk):
                wipe_job = await self.middleware.call(
                    'disk.wipe', disk, 'QUICK', False, {'configure_swap': False}
                )
                await wipe_job.wait()
                if wipe_job.error:
                    self.logger.warning('Failed to wipe disk %r: {%r}', disk, wipe_job.error)

            job.set_progress(80, 'Cleaning disks')
            await asyncio_map(unlabel, disks, limit=16)

            if await self.middleware.call('failover.licensed'):
                try:
                    await self.middleware.call('failover.call_remote', 'disk.retaste')
                except Exception as e:
                    ignore = (CallError.ENOMETHOD, errno.ECONNREFUSED, errno.ECONNABORTED, errno.EHOSTDOWN)
                    if isinstance(e, CallError) and e.errno in ignore:
                        pass
                    else:
                        self.logger.warning('Failed to retaste disks on standby controller', exc_info=True)

            job.set_progress(85, 'Syncing disk changes')
            djob = await self.middleware.call('disk.sync_all')
            await djob.wait()
            if djob.error:
                self.logger.warning('Failed syncing all disks: %r', djob.error)
        else:
            job.set_progress(80, 'Exporting pool')
            await self.middleware.call('zfs.pool.export', pool['name'])

        job.set_progress(90, 'Cleaning up after export')
        await self.middleware.run_in_thread(self.cleanup_after_export, pool, options)

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
        self.middleware.send_event('pool.query', 'REMOVED', id=oid)
