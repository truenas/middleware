import os
import platform
import shutil
import tempfile

from middlewared.service import private, Service
from middlewared.utils import run

IS_LINUX = platform.system().lower() == 'linux'


class BootService(Service):

    @private
    async def install_loader(self, dev):
        if IS_LINUX:
            await run('grub-install', '--target=i386-pc', f'/dev/{dev}')
            await run('mkdosfs', '-F', '32', '-s', '1', '-n', 'EFI', f'/dev/{dev}2')
            with tempfile.TemporaryDirectory() as tmpdirname:
                efi_dir = os.path.join(tmpdirname, 'efi')
                os.makedirs(efi_dir)
                await run('mount', '-t', 'vfat', f'/dev/{dev}2', efi_dir)
                await run(
                    'grub-install', '--target=x86_64-efi', f'--efi-directory={efi_dir}',
                    '--bootloader-id=debian', '--recheck', '--no-floppy',
                )
                mounted_efi_dir = os.path.join(efi_dir, 'EFI')
                os.makedirs(os.path.join(mounted_efi_dir, 'boot'), exist_ok=True)
                shutil.copy(
                    os.path.join(mounted_efi_dir, 'debian/grubx64.efi'),
                    os.path.join(mounted_efi_dir, 'boot/bootx64.efi')
                )
                await run('umount', efi_dir)
        else:
            if (await self.middleware.call('boot.get_boot_type')) == 'EFI':
                with tempfile.TemporaryDirectory() as tmpdirname:
                    await run('mount', '-t', 'msdosfs', f'/dev/{dev}p1', tmpdirname, check=False)
                    try:
                        os.makedirs(f'{tmpdirname}/efi/boot')
                    except FileExistsError:
                        pass
                    await run('cp', '/boot/boot1.efi', f'{tmpdirname}/efi/boot/BOOTx64.efi', check=False)
                    await run('umount', tmpdirname, check=False)
            else:
                await run(
                    'gpart', 'bootcode', '-b', '/boot/pmbr', '-p', '/boot/gptzfsboot', '-i', '1', f'/dev/{dev}',
                    check=False
                )
