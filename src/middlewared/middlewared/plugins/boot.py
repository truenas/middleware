import asyncio
import os

from pydantic import Field

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    BootGetDisksArgs, BootGetDisksResult, BootAttachArgs, BootAttachResult, BootDetachArgs,
    BootDetachResult, BootReplaceArgs, BootReplaceResult, BootScrubArgs, BootScrubResult,
    BootSetScrubIntervalArgs, BootSetScrubIntervalResult, BootGetStateArgs, BootGetStateResult
)
from middlewared.service import CallError, Service, job, private
from middlewared.utils import run, BOOT_POOL_NAME_VALID


BOOT_ATTACH_REPLACE_LOCK = 'boot_attach_replace'
BOOT_POOL_NAME = BOOT_POOL_DISKS = None


class BootUpdateInitramfsOptions(BaseModel):
    database: str | None = None
    force: bool = False


class BootUpdateInitramfsArgs(BaseModel):
    options: BootUpdateInitramfsOptions = Field(default_factory=BootUpdateInitramfsOptions)


class BootUpdateInitramfsResult(BaseModel):
    result: bool


class BootService(Service):

    class Config:
        cli_namespace = 'system.boot'

    @private
    async def pool_name(self):
        return BOOT_POOL_NAME

    @api_method(BootGetStateArgs, BootGetStateResult, roles=['READONLY_ADMIN'])
    async def get_state(self):
        """
        Returns the current state of the boot pool, including all vdevs, properties and datasets.
        """
        # WebUI expects same data as `pool.pool_extend`
        return await self.middleware.call('pool.pool_normalize_info', BOOT_POOL_NAME)

    @private
    async def get_disks_cache(self):
        """If boot pool disk cache hasn't been set (or cleared),
        then set it.

        NOTE: we cache this information since it doesn't change
        very often and we have a ton of callers (especially on HA)
        that need to determine this information. By caching this,
        it reduces the amount of times we have to use our ProcessPool
        """
        global BOOT_POOL_DISKS
        if BOOT_POOL_DISKS is None:
            # Using an immutable object is very important since this is
            # a globally cached value
            disks = list()
            args = {'name': BOOT_POOL_NAME, 'real_paths': True}
            for disk in (await self.middleware.call('zpool.status', args))['disks']:
                disks.append(disk)
            BOOT_POOL_DISKS = tuple(disks)
        return list(BOOT_POOL_DISKS)

    @private
    async def clear_disks_cache(self):
        """Clear the boot pool disk cache"""
        global BOOT_POOL_DISKS
        BOOT_POOL_DISKS = None

    @api_method(BootGetDisksArgs, BootGetDisksResult, roles=['DISK_READ'])
    async def get_disks(self):
        """
        Returns disks of the boot pool.
        """
        return await self.get_disks_cache()

    @private
    async def get_boot_type(self):
        """
        Get the boot type of the boot pool.

        Returns:
            "BIOS", "EFI", None
        """
        # https://wiki.debian.org/UEFI
        return 'EFI' if os.path.exists('/sys/firmware/efi') else 'BIOS'

    @api_method(BootAttachArgs, BootAttachResult, roles=['DISK_WRITE'])
    @job(lock=BOOT_ATTACH_REPLACE_LOCK)
    async def attach(self, job, dev, options):
        """
        Attach a disk to the boot pool, turning a stripe into a mirror.

        `expand` option will determine whether the new disk partition will be
                 the maximum available or the same size as the current disk.
        """
        await self.check_update_ashift_property()
        disks = list(await self.get_disks())
        if len(disks) > 1:
            raise CallError('3-way mirror not supported')

        format_opts = {}
        if not options['expand']:
            # Lets try to find out the size of the current ZFS or FreeBSD-ZFS (upgraded TrueNAS CORE installation)
            # partition so the new partition is not bigger, preventing size mismatch if one of them fail later on.
            if zfs_part := await self.middleware.call('disk.get_partition', disks[0]):
                format_opts['size'] = zfs_part['size_bytes']

        format_opts['legacy_schema'] = await self.legacy_schema(disks[0])

        await self.middleware.call('boot.format', dev, format_opts)

        pool = await self.middleware.call('zfs.pool.query', [['name', '=', BOOT_POOL_NAME]], {'get': True})

        zfs_dev_part = await self.middleware.call('disk.get_partition', dev)
        extend_pool_job = await self.middleware.call(
            'zfs.pool.extend', BOOT_POOL_NAME, None, [{
                'target': pool['groups']['data'][0]['guid'],
                'type': 'DISK',
                'path': f'/dev/{zfs_dev_part["name"]}'
            }]
        )

        await self.middleware.call('boot.install_loader', dev)

        await job.wrap(extend_pool_job)

        # If the user is upgrading his disks, let's set expand to True to make sure that we
        # register the new disks capacity which increase the size of the pool
        await self.middleware.call('zfs.pool.online', BOOT_POOL_NAME, zfs_dev_part['name'], True)
        await self.update_initramfs()

    @api_method(BootDetachArgs, BootDetachResult, roles=['DISK_WRITE'])
    async def detach(self, dev):
        """
        Detach given `dev` from boot pool.
        """
        await self.check_update_ashift_property()
        await self.middleware.call('zfs.pool.detach', BOOT_POOL_NAME, dev, {'clear_label': True})
        await self.update_initramfs()

    @api_method(BootReplaceArgs, BootReplaceResult, roles=['DISK_WRITE'])
    @job(lock=BOOT_ATTACH_REPLACE_LOCK)
    async def replace(self, job, label, dev):
        """
        Replace device `label` on boot pool with `dev`.
        """
        format_opts = {}
        await self.check_update_ashift_property()
        disks = list(await self.get_disks())

        format_opts['legacy_schema'] = await self.legacy_schema(disks[0])

        job.set_progress(0, f'Formatting {dev}')
        await self.middleware.call('boot.format', dev, format_opts)

        job.set_progress(0, f'Replacing {label} with {dev}')
        zfs_dev_part = await self.middleware.call('disk.get_partition', dev)
        await self.middleware.call('zfs.pool.replace', BOOT_POOL_NAME, label, zfs_dev_part['name'])

        # We need to wait for pool resilver after replacing a device, otherwise grub might
        # fail with `unknown filesystem` error
        while True:
            state = await self.get_state()
            if (
                state['scan'] and
                state['scan']['function'] == 'RESILVER' and
                state['scan']['state'] == 'SCANNING'
            ):
                left = int(state['scan']['total_secs_left']) if state['scan']['total_secs_left'] else 'unknown'
                job.set_progress(int(state['scan']['percentage']), f'Resilvering boot pool, {left} seconds left')
                await asyncio.sleep(5)
            else:
                break

        job.set_progress(100, 'Installing boot loader')
        await self.middleware.call('boot.install_loader', dev)
        await self.update_initramfs()

    @api_method(BootScrubArgs, BootScrubResult, roles=['BOOT_ENV_WRITE'])
    @job(lock='boot_scrub')
    async def scrub(self, job):
        """
        Scrub on boot pool.
        """
        subjob = await self.middleware.call('pool.scrub.scrub', BOOT_POOL_NAME)
        return await job.wrap(subjob)

    @api_method(BootSetScrubIntervalArgs, BootSetScrubIntervalResult, roles=['BOOT_ENV_WRITE'])
    async def set_scrub_interval(self, interval):
        """
        Set Automatic Scrub Interval value in days.
        """
        await self.middleware.call(
            'datastore.update',
            'system.advanced',
            (await self.middleware.call('system.advanced.config'))['id'],
            {'adv_boot_scrub': interval},
        )
        return interval

    @api_method(BootUpdateInitramfsArgs, BootUpdateInitramfsResult, private=True)
    async def update_initramfs(self, options):
        """
        Returns true if initramfs was updated and false otherwise.
        """
        args = ['/']
        if options['database']:
            args.extend(['-d', options['database']])
        if options['force']:
            args.extend(['-f'])

        cp = await run(
            '/usr/local/bin/truenas-initrd.py', *args,
            encoding='utf8', errors='ignore', check=False
        )
        if cp.returncode > 1:
            raise CallError(f'Failed to update initramfs: {cp.stdout} {cp.stderr}')

        return cp.returncode == 1

    @private
    async def expand(self):
        await self.check_update_ashift_property()
        boot_pool = await self.middleware.call('boot.pool_name')
        for device in await self.middleware.call('zfs.pool.get_devices', boot_pool):
            try:
                await self.expand_device(device)
            except CallError as e:
                self.middleware.logger.error('Error trying to expand boot pool partition %r: %r', device, e)
            except Exception:
                self.middleware.logger.error('Error trying to expand boot pool partition %r', device, exc_info=True)

    @private
    async def expand_device(self, device):
        disk = await self.middleware.call('disk.get_disk_from_partition', device)

        partitions = await self.middleware.call('device.get_disk_partitions', disk)
        if len(partitions) != 3:
            raise CallError(f'Expected 3 partitions, found {len(partitions)}')

        if partitions[-1]['name'] != device:
            raise CallError(f'{device} is not the last partition')

        if partitions[-1]['partition_number'] != 3:
            raise CallError(f'{device} is not 3rd partition')

        if partitions[-1]['start_sector'] != partitions[-2]['end_sector'] + 1:
            raise CallError(f'{device} does not immediately follow the 2nd partition')

        disk_size = await self.middleware.call('disk.get_dev_size', disk)
        if partitions[-1]['end'] > disk_size / 1.1:
            return

        self.middleware.logger.info('Resizing boot pool partition %r from %r (disk_size = %r)',
                                    device, partitions[-1]['end'], disk_size)
        await run('sgdisk', '-d', '3', f'/dev/{disk}', encoding='utf-8', errors='ignore')
        await run('sgdisk', '-N', '3', f'/dev/{disk}', encoding='utf-8', errors='ignore')
        await run('partprobe', encoding='utf-8', errors='ignore')
        await run('zpool', 'online', '-e', 'boot-pool', device, encoding='utf-8', errors='ignore')

    @private
    async def legacy_schema(self, disk):
        partitions = await self.middleware.call('device.get_disk_partitions', disk)
        swap_types = [
            '516e7cb5-6ecf-11d6-8ff8-00022d09712b',  # used by freebsd
            '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',  # used by linux
        ]
        partitions_without_swap = [p for p in partitions if p['partition_type'] not in swap_types]
        if (
            await self.middleware.call('boot.get_boot_type') == 'EFI' and
            len(partitions_without_swap) == 2 and
            partitions[0]['size'] == 524288
        ):
            return 'BIOS_ONLY'
        elif (
            len(partitions_without_swap) == 2 and
            partitions[0]['size'] == 272629760
        ):
            return 'EFI_ONLY'

    @private
    async def check_update_ashift_property(self):
        properties = {}
        if (
            zfs_pool := await self.middleware.call('zfs.pool.query', [('name', '=', BOOT_POOL_NAME)])
        ) and zfs_pool[0]['properties']['ashift']['source'] == 'DEFAULT':
            properties['ashift'] = {'value': '12'}

        if properties:
            await self.middleware.call('zfs.pool.update', BOOT_POOL_NAME, {'properties': properties})


async def on_config_upload(middleware, path):
    await middleware.call('boot.update_initramfs', {'database': path})


async def setup(middleware):
    global BOOT_POOL_NAME

    try:
        pools = dict([line.split('\t') for line in (
            await run('zpool', 'list', '-H', '-o', 'name,compatibility', encoding='utf8')
        ).stdout.strip().splitlines()])
    except Exception:
        # this isn't fatal, but we need to log something so we can review and fix as needed
        middleware.logger.warning('Unexpected failure parsing compatibility feature', exc_info=True)
        return

    for i in BOOT_POOL_NAME_VALID:
        if i in pools:
            BOOT_POOL_NAME = i
            await middleware.call('boot.get_disks')  # populates disk cache
            compatibility = pools[i]
            if compatibility != 'grub2':
                middleware.logger.info(f'Boot pool {BOOT_POOL_NAME!r} has {compatibility=!r}, setting it to grub2')
                try:
                    await run('zpool', 'set', 'compatibility=grub2', BOOT_POOL_NAME)
                except Exception as e:
                    middleware.logger.error(f'Error setting boot pool compatibility: {e!r}')

            break
    else:
        middleware.logger.error('Failed to detect boot pool name.')

    middleware.register_hook('config.on_upload', on_config_upload, sync=True)
