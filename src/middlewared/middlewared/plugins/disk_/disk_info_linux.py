import blkid
import os

from middlewared.service import CallError, Service

from .disk_info_base import DiskInfoBase


class DiskService(Service, DiskInfoBase):

    async def get_dev_size(self, dev):
        try:
            return blkid.BlockDevice(os.path.join('/dev', dev)).size
        except blkid.BlkidException:
            return None

    def list_partitions(self, disk):
        parts = []
        try:
            block_device = blkid.BlockDevice(os.path.join('/dev', disk))
        except blkid.BlkidException:
            return parts

        if not block_device.partitions_exist:
            return parts

        return [
            {
                'name': f'{disk}{p["partition_number"]}',
                'size': p['partition_size'],
                'partition_type': p['type'],
                'disk': disk,
                'id': f'{disk}{p["partition_number"]}',
                'path': os.path.join('/dev', f'{disk}{p["partition_number"]}')
            }
            for p in block_device.__getstate__()['partitions_data']['partitions']
        ]

    def gptid_from_part_type(self, disk, part_type):
        try:
            dev = blkid.BlockDevice(os.path.join('/dev', disk)).__getstate__()
        except blkid.BlkidException:
            raise CallError(f'{disk} not found')

        if not dev['partitions_exist']:
            raise CallError(f'{disk} has no partitions')

        part = next((p['part_uuid'] for p in dev['partitions_data']['partitions'] if p['type'] == part_type), None)
        if not part:
            raise CallError(f'Partition type {part_type} not found on {disk}')
        return f'disk/by-partuuid/{part}'

    async def get_zfs_part_type(self):
        return '6a898cc3-1dd2-11b2-99a6-080020736631'

    async def get_swap_part_type(self):
        return '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f'

    async def get_swap_devices(self, include_mirrors=False):
        with open('/proc/swaps', 'r') as f:
            data = f.read()
        devices = []
        for dev_line in filter(lambda l: l.startswith('/dev'), data.splitlines()):
            dev = dev_line.split()[0]
            if not include_mirrors and dev.startswith('/dev/md'):
                continue
            devices.append(dev)
        return devices
