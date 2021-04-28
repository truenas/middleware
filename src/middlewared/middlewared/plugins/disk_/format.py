import contextlib
import subprocess

from middlewared.service import CallError, private, Service
from middlewared.utils import osc


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

        # Calculate swap size.
        swapsize = swapgb * 1024 * 1024 * 1024 / (disk_details["sectorsize"] or 512)
        # Round up to nearest whole integral multiple of 128
        # so next partition starts at mutiple of 128.
        swapsize = (int((swapsize + 127) / 128)) * 128

        commands = [] if osc.IS_LINUX else [('gpart', 'create', '-s', 'gpt', f'/dev/{disk}')]
        if swapsize > 0:
            if osc.IS_LINUX:
                commands.extend([
                    (
                        'sgdisk', f'-a{int(4096/disk_details["sectorsize"])}',
                        f'-n1:128:{swapsize}', '-t1:8200', f'/dev/{disk}'
                    ),
                    ('sgdisk', '-n2:0:0', '-t2:BF01', f'/dev/{disk}'),
                ])
            else:
                commands.extend([
                    ('gpart', 'add', '-a', '4k', '-b', '128', '-t', 'freebsd-swap', '-s', str(swapsize), disk),
                    ('gpart', 'add', '-a', '4k', '-t', 'freebsd-zfs', disk),
                ])
        else:
            if osc.IS_LINUX:
                commands.append(
                    ('sgdisk', f'-a{int(4096/disk_details["sectorsize"])}', '-n1:0:0', '-t1:BF01', f'/dev/{disk}'),
                )
            else:
                commands.append(('gpart', 'add', '-a', '4k', '-b', '128', '-t', 'freebsd-zfs', disk))

        # Install a dummy boot block so system gives meaningful message if booting
        # from the wrong disk.
        if osc.IS_FREEBSD:
            commands.append(('gpart', 'bootcode', '-b', '/boot/pmbr-datadisk', f'/dev/{disk}'))
        # TODO: Let's do the same for linux please ^^^

        for command in commands:
            cp = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )
            if cp.returncode != 0:
                raise CallError(f'Unable to GPT format the disk "{disk}": {cp.stderr}')

        if osc.IS_LINUX:
            self.middleware.call_sync('device.settle_udev_events')

        for partition in self.middleware.call_sync('disk.list_partitions', disk):
            with contextlib.suppress(CallError):
                # It's okay to suppress this as some partitions might not have it
                self.middleware.call_sync('zfs.pool.clear_label', partition['path'])

        if sync:
            # We might need to sync with reality (e.g. devname -> uuid)
            self.middleware.call_sync('disk.sync', disk)
