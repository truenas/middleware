import os
import shutil
import tempfile

from middlewared.service import Service, private
from middlewared.utils import run
from middlewared.utils.mount import umount


class BootService(Service):

    @private
    async def install_loader(self, dev):
        legacy_schema = await self.middleware.call('boot.legacy_schema', dev)

        if legacy_schema == 'EFI_ONLY':
            efi_partition_number = 1
        else:
            efi_partition_number = 2
            await run('grub-install', '--target=i386-pc', f'/dev/{dev}')

        if legacy_schema == 'BIOS_ONLY':
            return

        partition = await self.middleware.call('disk.get_partition_for_disk', dev, efi_partition_number)
        await run('mkdosfs', '-F', '32', '-s', '1', '-n', 'EFI', f'/dev/{partition}')
        with tempfile.TemporaryDirectory() as tmpdirname:
            efi_dir = os.path.join(tmpdirname, 'efi')
            os.makedirs(efi_dir)
            await run('mount', '-t', 'vfat', f'/dev/{partition}', efi_dir)
            grub_cmd = [
                'grub-install', '--target=x86_64-efi', f'--efi-directory={efi_dir}',
                '--bootloader-id=debian', '--recheck', '--no-floppy',
            ]
            if not os.path.exists('/sys/firmware/efi'):
                grub_cmd.append('--no-nvram')
            await run(*grub_cmd)
            mounted_efi_dir = os.path.join(efi_dir, 'EFI')
            os.makedirs(os.path.join(mounted_efi_dir, 'boot'), exist_ok=True)
            shutil.copy(
                os.path.join(mounted_efi_dir, 'debian/grubx64.efi'),
                os.path.join(mounted_efi_dir, 'boot/bootx64.efi')
            )
            await self.middleware.run_in_thread(umount, efi_dir)
