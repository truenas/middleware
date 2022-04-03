import contextlib
import subprocess

from middlewared.service import CallError, private, Service

# from parttypes.cc
SWAP_PARTHEX = '8200'
ZFS_PARTHEX = 'BF01'


class DiskService(Service):

    @private
    def format(self, disk, swapgb, sync=True):
        disk_details = self.middleware.call_sync('device.get_disk', disk)
        if not disk_details:
            raise CallError(f'Unable to retrieve disk details for {disk}')
        size = disk_details['size']
        if not size:
            self.logger.error(f'Unable to determine size of {disk}')
        else:
            # The GPT header takes about 34KB + alignment, round it to 100
            if size - 102400 <= swapgb * 1024 * 1024 * 1024:
                raise CallError(f'Your disk size must be higher than {swapgb}GB')

        job = self.middleware.call_sync('disk.wipe', disk, 'QUICK', sync)
        job.wait_sync()
        if job.error:
            raise CallError(f'Failed to wipe disk {disk}: {job.error}')

        sectorsize = disk_details['sectorsize'] or 512

        # Calculate swap size.
        swapsize = swapgb * 1024 * 1024 * 1024 / sectorsize
        # Round up to nearest whole integral multiple of 128
        # so next partition starts at mutiple of 128.
        swapsize = (int((swapsize + 127) / 128)) * 128

        alignment = int(4096 / sectorsize)
        if swapsize > 0:
            commands = [
                ('sgdisk', f'-a{alignment}', f'-n1:128:{swapsize}', f'-t1:{SWAP_PARTHEX}', f'/dev/{disk}'),
                ('sgdisk', '-n2:0:0', f'-t2:{ZFS_PARTHEX}', f'/dev/{disk}'),
            ]
        else:
            commands = [('sgdisk', f'-a{alignment}', '-n1:0:0', f'-t1:{ZFS_PARTHEX}', f'/dev/{disk}')]

        # TODO: Install a dummy boot block so system gives meaningful message if booting from a zpool data disk.

        for cmd in commands:
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if cp.returncode != 0:
                raise CallError(f'Unable to GPT format the disk "{disk}": {cp.stderr}')

        self.middleware.call_sync('device.settle_udev_events')

        for partition in self.middleware.call_sync('disk.list_partitions', disk):
            with contextlib.suppress(CallError):
                # It's okay to suppress this as some partitions might not have it
                self.middleware.call_sync('zfs.pool.clear_label', partition['path'])

        if sync:
            # We might need to sync with reality (e.g. devname -> uuid)
            self.middleware.call_sync('disk.sync', disk)
