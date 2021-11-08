from asyncio import ensure_future
from errno import ENOENT
from os.path import exists

from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.service import item_method, job, Service, ValidationErrors


class PoolService(Service):

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
        Str('disk', required=True),
        Bool('force', default=False),
        Str('passphrase', private=True),
    ))
    @job(lock='pool_replace')
    async def replace(self, job, oid, options):
        """
        Replace a disk on a pool.

        `label` is the ZFS guid or a device name
        `disk` is the identifier of a disk
        `passphrase` is only valid for TrueNAS Core/Enterprise platform where pool is GELI encrypted

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
        pool = await self.get_instance(oid)

        verrors = ValidationErrors()
        unused_disks = await self.middleware.call('disk.get_unused')
        disk = list(filter(lambda x: x['identifier'] == options['disk'], unused_disks))
        if not disk:
            verrors.add('options.disk', f'Disk "{options["disk"]}" not found.', ENOENT)
        else:
            disk = disk[0]
            if not options['force'] and not await self.middleware.call('disk.check_clean', disk['devname']):
                verrors.add('options.force', 'Disk is not clean, partitions were found.')

        if pool['encrypt'] == 2:
            if not options.get('passphrase'):
                verrors.add('options.passphrase', 'Passphrase is required for encrypted pool.')
            elif not await self.middleware.call('disk.geli_testkey', pool, options['passphrase']):
                verrors.add('options.passphrase', 'Passphrase is not valid.')

        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found.', ENOENT)
        verrors.check()

        swap_disks = [disk['devname']]
        # If the disk we are replacing is still available, remove it from swap as well
        if found[1] and exists(found[1]['path']):
            from_disk = await self.middleware.call('disk.label_to_disk', found[1]['path'].replace('/dev/', ''))
            if from_disk:
                swap_disks.append(from_disk)
        await self.middleware.call('disk.swaps_remove_disks', swap_disks)

        await self.middleware.call(
            'pool.format_and_encrypt_disks', job,
            {disk['devname']: {'create_swap': found[0] in ('data', 'spare')}},
            {'enc_keypath': pool['encryptkey_path'], 'passphrase': options.get('passphrase')},
        )
        await self.middleware.call('geom.invalidate_cache')

        zfs_part = await self.middleware.call('disk.get_zfs_part_type')
        new_devname = await self.middleware.call('disk.gptid_from_part_type', disk['devname'], zfs_part)
        if pool['encrypt'] > 0:
            new_devname = f'{new_devname}.eli'

        job.set_progress(30, 'Replacing disk')
        try:
            await self.middleware.call('zfs.pool.replace', pool['name'], options['label'], new_devname)
            # If we are replacing a faulted disk, kick it right after replace is initiated.
            try:
                vdev = await self.middleware.call('zfs.pool.get_vdev', pool['name'], options['label'])
                if vdev['status'] not in ('ONLINE', 'DEGRADED'):
                    await self.middleware.call('zfs.pool.detach', pool['name'], options['label'])
            except Exception:
                self.logger.warning('Failed to detach device', exc_info=True)
        except Exception:
            try:
                # If replace has failed lets detach geli to not keep disk busy
                await self.middleware.call('disk.geli_detach_single', new_devname)
            except Exception:
                self.logger.warning(f'Failed to geli detach {new_devname}', exc_info=True)
                raise
            finally:
                # Needs to happen even if replace failed to put back disk that had been
                # removed from swap prior to replacement
                ensure_future(self.middleware.call('disk.swaps_configure'))

        enc_disks = {'disk': disk['devname'], 'devname': f'/dev/{new_devname}'}
        await self.middleware.call('pool.save_encrypteddisks', oid, enc_disks, {disk['devname']: disk})

        return True
