import os
import tempfile

from middlewared.service import private, Service
from middlewared.utils import osc
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def format_disks(self, job, disks, disk_encryption_options=None):
        """
        Format all disks, putting all freebsd-zfs partitions created
        into their respective vdevs and encrypting disks if specified for FreeBSD.
        """
        # Make sure all SED disks are unlocked
        await self.middleware.call('disk.sed_unlock_all')
        disk_encryption_options = disk_encryption_options or {}

        swapgb = (await self.middleware.call('system.advanced.config'))['swapondrive']

        enc_disks = []
        formatted = 0

        async def format_disk(arg):
            nonlocal enc_disks, formatted
            disk, config = arg
            await self.middleware.call(
                'disk.format', disk, swapgb if config['create_swap'] else 0, False,
            )
            devname = await self.middleware.call(
                'disk.gptid_from_part_type', disk, await self.middleware.call('disk.get_zfs_part_type')
            )
            if osc.IS_FREEBSD and disk_encryption_options.get('enc_keypath'):
                enc_disks.append({
                    'disk': disk,
                    'devname': devname,
                })
                devname = await self.middleware.call(
                    'disk.encrypt', devname, disk_encryption_options['enc_keypath'],
                    disk_encryption_options.get('passphrase_path')
                )
            formatted += 1
            job.set_progress(15, f'Formatting disks ({formatted}/{len(disks)})')
            config['vdev'].append(f'/dev/{devname}')

        job.set_progress(15, f'Formatting disks (0/{len(disks)})')

        pass_file = None
        if osc.IS_FREEBSD and disk_encryption_options.get('passphrase'):
            pass_file = await self.middleware.call('pool.create_temp_pass_file', disk_encryption_options['passphrase'])
            disk_encryption_options['passphrase_path'] = pass_file

        try:
            await asyncio_map(format_disk, disks.items(), limit=16)
        finally:
            if pass_file:
                await self.middleware.call('pool.destroy_temp_pass_file', pass_file)

        await self.middleware.call('disk.sync_all')

        return enc_disks

    @private
    def create_temp_pass_file(self, content):
        passf = tempfile.NamedTemporaryFile(mode='w+', dir='/tmp/', delete=False)
        os.chmod(passf.name, 0o600)
        passf.write(content)
        passf.flush()
        pass_file = passf.name
        passf.close()
        return pass_file

    @private
    def destroy_temp_pass_file(self, path):
        if os.path.exists(path):
            os.unlink(path)
