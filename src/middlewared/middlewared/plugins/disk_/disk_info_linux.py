import blkid
import glob
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

        for p in block_device.__getstate__()['partitions_data']['partitions']:
            if disk.startswith('nvme'):
                # This is a hack for nvme disks, however let's please come up with a better way
                # to link disks with their partitions
                part_name = f'{disk}p{p["partition_number"]}'
            else:
                part_name = f'{disk}{p["partition_number"]}'
            part = {
                'name': part_name,
                'size': p['partition_size'],
                'partition_type': p['type'],
                'partition_number': p['partition_number'],
                'partition_uuid': p['part_uuid'],
                'disk': disk,
                'id': part_name,
                'path': os.path.join('/dev', part_name),
                'encrypted_provider': None,
            }
            encrypted_provider = glob.glob(f'/sys/block/dm-*/slaves/{part["name"]}')
            if encrypted_provider:
                part['encrypted_provider'] = os.path.join('/dev', encrypted_provider[0].split('/')[3])
            parts.append(part)
        return parts

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

    def get_swap_devices(self):
        with open('/proc/swaps', 'r') as f:
            data = f.read()
        devices = []
        for dev_line in filter(lambda l: l.startswith('/dev'), data.splitlines()):
            devices.append(dev_line.split()[0])
        return devices

    def label_to_dev(self, label, *args):
        dev = os.path.realpath(os.path.join('/dev', label)).split('/')[-1]
        return dev if dev != label.split('/')[-1] else None

    def label_to_disk(self, label, *args):
        part_disk = self.label_to_dev(label)
        return self.get_disk_from_partition(part_disk) if part_disk else None

    def get_disk_from_partition(self, part_name):
        if not os.path.exists(os.path.join('/dev', part_name)):
            return None
        with open(os.path.join('/sys/class/block', part_name, 'partition'), 'r') as f:
            part_num = f.read().strip()
        if part_name.startswith('nvme'):
            # nvme partitions would be like nvmen1p1 where disk is nvmen1
            part_num = f'p{part_num}'
        return part_name.rsplit(part_num, 1)[0].strip()
