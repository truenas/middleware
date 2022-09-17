import asyncio
import os

from middlewared.schema import accepts, Bool, Dict, Int, List, Str, returns, Patch
from middlewared.service import CallError, Service, job, private
from middlewared.utils import run
from middlewared.validators import Range

try:
    from bsd import geom
except ImportError:
    geom = None


BOOT_ATTACH_REPLACE_LOCK = 'boot_attach_replace'
BOOT_POOL_NAME = None
BOOT_POOL_NAME_VALID = ['freenas-boot', 'boot-pool']


class BootService(Service):

    class Config:
        cli_namespace = 'system.boot'

    @private
    async def pool_name(self):
        return BOOT_POOL_NAME

    @accepts()
    @returns(Patch(
        'pool_entry', 'get_state',
        ('rm', {'name': 'id'}),
        ('rm', {'name': 'guid'}),
        ('rm', {'name': 'encrypt'}),
        ('rm', {'name': 'encryptkey'})
    ))
    async def get_state(self):
        """
        Returns the current state of the boot pool, including all vdevs, properties and datasets.
        """
        # WebUI expects same data as `pool.pool_extend`
        return await self.middleware.call('pool.pool_normalize_info', BOOT_POOL_NAME)

    @accepts()
    @returns(List('disks', items=[Str('disk')]))
    async def get_disks(self):
        """
        Returns disks of the boot pool.
        """
        return await self.middleware.call('zfs.pool.get_disks', BOOT_POOL_NAME)

    @private
    async def get_boot_type(self):
        """
        Get the boot type of the boot pool.

        Returns:
            "BIOS", "EFI", None
        """
        # https://wiki.debian.org/UEFI
        return 'EFI' if os.path.exists('/sys/firmware/efi') else 'BIOS'

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Bool('expand', default=False),
        ),
    )
    @returns()
    @job(lock=BOOT_ATTACH_REPLACE_LOCK)
    async def attach(self, job, dev, options):
        """
        Attach a disk to the boot pool, turning a stripe into a mirror.

        `expand` option will determine whether the new disk partition will be
                 the maximum available or the same size as the current disk.
        """

        disks = list(await self.get_disks())
        if len(disks) > 1:
            raise CallError('3-way mirror not supported')

        format_opts = {}
        if not options['expand']:
            # Lets try to find out the size of the current ZFS or FreeBSD-ZFS (upgraded TrueNAS CORE installation)
            # partition so the new partition is not bigger, preventing size mismatch if one of them fail later on.
            zfs_part = await self.middleware.call(
                'disk.get_partition_with_uuids',
                disks[0],
                await self.middleware.call('disk.get_valid_zfs_partition_type_uuids'),
            )
            if zfs_part:
                format_opts['size'] = zfs_part['size']

        swap_part = await self.middleware.call('disk.get_partition', disks[0], 'SWAP')
        if swap_part:
            format_opts['swap_size'] = swap_part['size']
        await self.middleware.call('boot.format', dev, format_opts)

        pool = await self.middleware.call('zfs.pool.query', [['name', '=', BOOT_POOL_NAME]], {'get': True})

        zfs_dev_part = await self.middleware.call('disk.get_partition', dev, 'ZFS')
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

    @accepts(Str('dev'))
    @returns()
    async def detach(self, dev):
        """
        Detach given `dev` from boot pool.
        """
        await self.middleware.call('zfs.pool.detach', BOOT_POOL_NAME, dev, {'clear_label': True})
        await self.update_initramfs()

    @accepts(Str('label'), Str('dev'))
    @returns()
    @job(lock=BOOT_ATTACH_REPLACE_LOCK)
    async def replace(self, job, label, dev):
        """
        Replace device `label` on boot pool with `dev`.
        """
        format_opts = {}
        disks = list(await self.get_disks())
        swap_part = await self.middleware.call('disk.get_partition', disks[0], 'SWAP')
        if swap_part:
            format_opts['swap_size'] = swap_part['size']

        job.set_progress(0, f'Formatting {dev}')
        await self.middleware.call('boot.format', dev, format_opts)

        job.set_progress(0, f'Replacing {label} with {dev}')
        zfs_dev_part = await self.middleware.call('disk.get_partition', dev, 'ZFS')
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

    @accepts()
    @returns()
    @job(lock='boot_scrub')
    async def scrub(self, job):
        """
        Scrub on boot pool.
        """
        subjob = await self.middleware.call('pool.scrub.scrub', BOOT_POOL_NAME)
        return await job.wrap(subjob)

    @accepts(
        Int('interval', validators=[Range(min=1)])
    )
    @returns(Int('interval'))
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

    @accepts()
    @returns(Int('interval'))
    async def get_scrub_interval(self):
        """
        Get Automatic Scrub Interval value in days.
        """
        return (await self.middleware.call('system.advanced.config'))['boot_scrub']

    @private
    async def update_initramfs(self):
        """
        Returns true if initramfs was updated and false otherwise.
        """
        cp = await run(
            '/usr/local/bin/truenas-initrd.py', '/', encoding='utf8', errors='ignore', check=False
        )
        if cp.returncode > 1:
            raise CallError(f'Failed to update initramfs: {cp.stderr}')

        return cp.returncode == 1

    @private
    async def expand(self):
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

        partitions = await self.middleware.call('disk.list_partitions', disk)
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


async def setup(middleware):
    global BOOT_POOL_NAME

    pools = (
        await run('zpool', 'list', '-H', '-o', 'name', encoding='utf8')
    ).stdout.strip().split()
    for i in BOOT_POOL_NAME_VALID:
        if i in pools:
            BOOT_POOL_NAME = i
            break
    else:
        middleware.logger.error('Failed to detect boot pool name.')
