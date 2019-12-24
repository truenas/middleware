import os
import tempfile

from middlewared.service import Service
from middlewared.utils import run

from .boot_loader_base import BootLoaderBase


class BootService(Service, BootLoaderBase):

    async def install_loader(self, dev):
        if (await self.middleware.call('boot.get_boot_type')) == 'EFI':
            with tempfile.TemporaryDirectory() as tmpdirname:
                await run('mount', '-t', 'msdosfs', f'/dev/{dev}p1', tmpdirname, check=False)
                os.makedirs(f'{tmpdirname}/efi/boot', exist_ok=True)
                await run('cp', '/boot/boot1.efi', f'{tmpdirname}/efi/boot/BOOTx64.efi', check=False)
                await run('umount', tmpdirname, check=False)
        else:
            await run(
                'gpart', 'bootcode', '-b', '/boot/pmbr', '-p', '/boot/gptzfsboot', '-i', '1', f'/dev/{dev}',
                check=False
            )
