import os

from middlewared.schema import accepts, Bool, Datetime, Dict, Float, Int, List, Str, returns
from middlewared.service import CallError, Service, job, private
from middlewared.utils import osc, run
from middlewared.validators import Range

try:
    from bsd import geom
except ImportError:
    geom = None


BOOT_POOL_NAME = None
BOOT_POOL_NAME_VALID = ['freenas-boot', 'boot-pool']


class BootService(Service):

    class Config:
        cli_namespace = 'system.boot'

    @private
    async def pool_name(self):
        return BOOT_POOL_NAME

    @accepts()
    @returns(
        Dict(
            'boot_pool_state',
            Str('name'),
            Str('id'),
            Str('guid'),
            Str('hostname'),
            Str('status'),
            Bool('healthy'),
            Int('error_count'),
            Dict(
                'root_dataset',
                Str('id'),
                Str('name'),
                Str('pool'),
                Str('type'),
                Dict(
                    'properties',
                    additional_attrs=True,
                ),
                Str('mountpoint', null=True),
                Bool('encrypted'),
                Str('encryption_root', null=True),
                Bool('key_loaded'),
            ),
            Dict(
                'properties',
                additional_attrs=True,
            ),
            List('features', items=[Dict(
                'feature_item',
                Str('name'),
                Str('guid'),
                Str('description'),
                Str('state'),
            )]),
            Dict(
                'scan',
                Str('function'),
                Str('state'),
                Datetime('start_time', null=True),
                Datetime('end_time', null=True),
                Float('percentage'),
                Int('bytes_to_process'),
                Int('bytes_processed'),
                Datetime('pause', null=True),
                Int('errors'),
                Int('bytes_issued', null=True),
                Int('total_secs_left', null=True),

            ),
            Dict(
                'root_vdev',
                Str('type'),
                Str('path', null=True),
                Str('guid'),
                Str('status'),
                Dict(
                    'stats',
                    Int('timestamp'),
                    Int('read_errors'),
                    Int('write_errors'),
                    Int('checksum_errors'),
                    List('ops', items=[Int('op')]),
                    List('bytes', items=[Int('byte')]),
                    Int('size'),
                    Int('allocated'),
                    Int('fragmentation'),
                    Int('self_healed'),
                    Int('configured_ashift'),
                    Int('logical_ashift'),
                    Int('physical_ashift'),
                ),
            ),
            Dict(
                'groups',
                additional_attrs=True,
            ),
            Str('status_code'),
            Str('status_detail'),
        ),
    )
    async def get_state(self):
        """
        Returns the current state of the boot pool, including all vdevs, properties and datasets.
        """
        return await self.middleware.call('zfs.pool.query', [('name', '=', BOOT_POOL_NAME)], {'get': True})

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
        if osc.IS_LINUX:
            # https://wiki.debian.org/UEFI
            return 'EFI' if os.path.exists('/sys/firmware/efi') else 'BIOS'
        else:
            return await self.__get_boot_type_freebsd()

    async def __get_boot_type_freebsd(self):
        await self.middleware.run_in_thread(geom.scan)
        labelclass = geom.class_by_name('PART')
        efi = bios = 0
        for disk in await self.get_disks():
            for e in labelclass.xml.findall(f".//geom[name='{disk}']/provider/config/type"):
                if e.text == 'efi':
                    efi += 1
                elif e.text == 'freebsd-boot':
                    bios += 1
        if efi == 0 and bios == 0:
            return None
        if bios > 0:
            return 'BIOS'
        return 'EFI'

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Bool('expand', default=False),
        ),
    )
    @returns()
    @job(lock='boot_attach')
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
            # Lets try to find out the size of the current freebsd-zfs partition so
            # the new partition is not bigger, preventing size mismatch if one of
            # them fail later on. See #21336
            zfs_part = await self.middleware.call('disk.get_partition', disks[0], 'ZFS')
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
    async def replace(self, label, dev):
        """
        Replace device `label` on boot pool with `dev`.
        """
        format_opts = {}
        disks = list(await self.get_disks())
        swap_part = await self.middleware.call('disk.get_partition', disks[0], 'SWAP')
        if swap_part:
            format_opts['swap_size'] = swap_part['size']

        await self.middleware.call('boot.format', dev, format_opts)
        zfs_dev_part = await self.middleware.call('disk.get_partition', dev, 'ZFS')
        await self.middleware.call('zfs.pool.replace', BOOT_POOL_NAME, label, zfs_dev_part['name'])
        await self.middleware.call('boot.install_loader', dev)
        await self.update_initramfs()

    @accepts()
    @returns()
    @job(lock='boot_scrub')
    async def scrub(self, job):
        """
        Scrub on boot pool.
        """
        subjob = await self.middleware.call('zfs.pool.scrub', BOOT_POOL_NAME)
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
