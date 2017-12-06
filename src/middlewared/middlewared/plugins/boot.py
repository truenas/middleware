from middlewared.schema import Bool, Dict, Int, Str, accepts
from middlewared.service import CallError, Service, private
from middlewared.utils import run

from bsd import geom

import asyncio


class BootService(Service):

    @accepts()
    async def get_disks(self):
        """
        Returns disks of the boot pool.
        """
        return await self.middleware.call('zfs.pool.get_disks', 'freenas-boot')

    @private
    async def get_boot_type(self):
        """
        Get the boot type of the boot pool.

        Returns:
            "BIOS", "EFI", None
        """
        await self.middleware.run_in_thread(geom.scan)
        labelclass = geom.class_by_name('PART')
        efi = bios = 0
        async for disk in await self.get_disks():
            for e in labelclass.xml.findall(f".//geom[name='{disk}']/provider/config/type"):
                if e.text == 'efi':
                    efi += 1
                elif e.text == 'bios-boot':
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
            Int('size'),
        )
    )
    @private
    async def format(self, dev, options):
        """
        Format a given disk `dev` using the appropiate partition layout
        """

        job = await self.middleware.call('disk.wipe', dev, 'QUICK')
        await job.wait()

        commands = []
        commands.append(['gpart', 'create', '-s', 'gpt', '-f', 'active', f'/dev/{dev}'])
        boottype = await self.get_boot_type()
        if boottype != 'EFI':
            commands.append(['gpart', 'add', '-t', 'bios-boot', '-i', '1', '-s', '512k', dev])
            commands.append(['gpart', 'set', '-a', 'active', dev])
        else:
            commands.append(['gpart', 'add', '-t', 'efi', '-i', '1', '-s', '260m', dev])
            commands.append(['newfs_msdos', '-F', '16', f'/dev/{dev}p1'])
            commands.append(['gpart', 'set', '-a', 'lenovofix', dev])
        commands.append(
            ['gpart', 'add', '-t', 'freebsd-zfs', '-i', '2', '-a', '4k'] + (
                ['-s', str(options['size']) + 'B'] if options.get('size') else []
            ) + [dev]
        )
        for command in commands:
            await run(*command)
        return boottype

    @private
    async def install_grub(self, boottype, dev):
        args = [
            '/usr/local/sbin/grub-install',
            '--modules=zfs part_gpt',
        ]

        if boottype == 'EFI':
            await run('mount', '-t', 'msdosfs', f'/dev/{dev}p1', '/boot/efi', check=False)
            args += ['--efi-directory=/boot/efi', '--removable', '--target=x86_64-efi']

        args.append(f'/dev/{dev}')

        await run(*args, check=False)

        if boottype == 'EFI':
            await run('umount', '/boot/efi', check=False)

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Bool('expand', default=False),
        ),
    )
    async def attach(self, dev, options=None):
        """
        Attach a disk to the boot pool, turning a stripe into a mirror.

        `expand` option will determine whether the new disk partition will be
                 the maximum available or the same size as the current disk.
        """

        disks = [d async for d in await self.get_disks()]
        if len(disks) > 1:
            raise CallError('3-way mirror not supported yet')

        format_opts = {}
        if not options['expand']:
            # Lets try to find out the size of the current freebsd-zfs partition so
            # the new partition is not bigger, preventing size mismatch if one of
            # them fail later on. See #21336
            await self.middleware.run_in_thread(geom.scan)
            labelclass = geom.class_by_name('PART')
            for e in labelclass.xml.findall(f"./geom[name='{disks[0]}']/provider/config[type='freebsd-zfs']"):
                format_opts['size'] = int(e.find('./length').text)
                break

        boottype = await self.format(dev, format_opts)

        await self.middleware.call('zfs.pool.extend', 'freenas-boot', None, [{'target': f'{disks[0]}p2', 'type': 'DISK', 'path': f'/dev/{dev}p2'}])

        # We need to wait a little bit to install grub onto the new disk
        # FIXME: use event for when its ready instead of sleep
        await asyncio.sleep(10)
        await self.install_grub(boottype, dev)

    @accepts(Str('dev'))
    async def detach(self, dev):
        """
        Detach given `dev` from boot pool.
        """
        await self.middleware.call('zfs.pool.detach', 'freenas-boot', dev)

    @accepts(Str('label'), Str('dev'))
    async def replace(self, label, dev):
        """
        Replace device `label` on boot pool with `dev`.
        """

        boottype = await self.format(dev)

        await self.middleware.call('zfs.pool.replace', 'freenas-boot', label, f'{dev}p2')

        # We need to wait a little bit to install grub onto the new disk
        # FIXME: use event for when its ready instead of sleep
        await asyncio.sleep(10)
        await self.install_grub(boottype, dev)
