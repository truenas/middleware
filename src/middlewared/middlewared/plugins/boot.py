from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import Service, private
from middlewared.utils import run

from bsd import geom


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
        await self.middleware.threaded(geom.scan)
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


    @accepts(Str('dev'))
    @private
    async def format(self, dev):
        """
        Format a given disk `dev` using the appropiate partition layout
        """
        commands = []
        commands.append(['gpart', 'create', '-s', 'gpt', '-f', 'active', f'/dev/{dev}'])
        boottype = await self.get_boot_type()
        if boottype != 'EFI':
            commands.append(['gpart', 'add', '-t', 'bios-boot', '-i', '1', '-s', '512k', dev])
            commands.append(['gpart', 'set', '-a', 'active', dev])
        else:
            commands.append(['gpart', 'add', '-t', 'efi', '-i', '1', '-s', '100m', dev])
            commands.append(['newfs_msdos', '-F', '16', f'/dev/{dev}p1'])
            commands.append(['gpart', 'set', '-a', 'lenovofix', dev])
        commands.append(['gpart', 'add', '-t', 'freebsd-zfs', '-i', '2', '-a', '4k', dev])
        for command in commands:
            await run(*command)
        return boottype

    @accepts(Str('dev'))
    async def attach(self, dev):

        disks = [d async for d in await self.get_disks()]
        if len(disks) > 1:
            raise CallError('3-way mirror not supported yet')

        await self.format(dev)

        await self.middleware.call('zfs.pool.extend', 'freenas-boot', None, [{'target': f'{disks[0]}p2', 'type': 'DISK', 'path': f'/dev/{dev}p2'}])
