import blkid
import os

from middlewared.service import Service

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
            {'name': f'{disk}{p["partition_number"]}', 'size': p['partition_size']}
            for p in block_device.__getstate__()['partitions_data']['partitions']
        ]
