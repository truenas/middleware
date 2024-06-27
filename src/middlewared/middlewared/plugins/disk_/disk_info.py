import glob
import os
import pathlib

import pyudev

from middlewared.service import CallError, private, Service


class DiskService(Service):

    @private
    def get_dev_size(self, device):
        try:
            dev = pyudev.Devices.from_name(pyudev.Context(), 'block', device)
        except pyudev.DeviceNotFoundByNameError:
            return
        else:
            if dev.get('DEVTYPE') not in ('disk', 'partition'):
                return

        return dev.attributes.asint('size') * 512

    @private
    def list_partitions(self, disk):
        parts = []
        try:
            bd = pyudev.Devices.from_name(pyudev.Context(), 'block', disk)
        except pyudev.DeviceNotFoundByNameError:
            return parts

        if not bd.children:
            return parts

        req_keys = ('ID_PART_' + i for i in ('TYPE', 'UUID', 'NUMBER', 'SIZE'))
        for p in filter(lambda p: all(p.get(k) for k in req_keys), bd.children):
            part_name = self.get_partition_for_disk(disk, p['ID_PART_ENTRY_NUMBER'])
            start_sector = int(p['ID_PART_ENTRY_OFFSET'])
            end_sector = int(p['ID_PART_ENTRY_OFFSET']) + int(p['ID_PART_ENTRY_SIZE']) - 1
            part = {
                'name': part_name,
                'partition_type': p['ID_PART_ENTRY_TYPE'],
                'partition_number': int(p['ID_PART_ENTRY_NUMBER']),
                'partition_uuid': p['ID_PART_ENTRY_UUID'],
                'disk': disk,
                'start_sector': start_sector,
                'start': start_sector * 512,
                'end_sector': end_sector,
                'end': end_sector * 512,
                'size': int(p['ID_PART_ENTRY_SIZE']) * 512,
                'id': part_name,
                'path': os.path.join('/dev', part_name),
                'encrypted_provider': None,
            }

            encrypted_provider = glob.glob(f'/sys/block/dm-*/slaves/{part["name"]}')
            if encrypted_provider:
                part['encrypted_provider'] = os.path.join('/dev', encrypted_provider[0].split('/')[3])
            parts.append(part)
        return parts

    @private
    def gptid_from_part_type(self, disk, part_type):
        try:
            block_device = pyudev.Devices.from_name(pyudev.Context(), 'block', disk)
        except pyudev.DeviceNotFoundByNameError:
            raise CallError(f'{disk} not found')

        if not block_device.children:
            raise CallError(f'{disk} has no partitions')

        part = next(
            (p['ID_PART_ENTRY_UUID'] for p in block_device.children if all(
                p.get(k) for k in ('ID_PART_ENTRY_UUID', 'ID_PART_ENTRY_TYPE')
            ) and p['ID_PART_ENTRY_TYPE'] == part_type), None
        )
        if not part:
            raise CallError(f'Partition type {part_type} not found on {disk}')
        return f'disk/by-partuuid/{part}'

    @private
    async def get_efi_part_type(self):
        return 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'

    @private
    async def get_zfs_part_type(self):
        return '6a898cc3-1dd2-11b2-99a6-080020736631'

    @private
    def label_to_dev(self, label):
        label_path = os.path.join('/dev', label)
        if not os.path.exists(label_path):
            return None

        dev = os.path.basename(os.path.realpath(label_path))
        if not pathlib.Path(os.path.join('/dev/', dev)).is_block_device():
            return None

        return dev

    @private
    def label_to_disk(self, label):
        partition_or_disk = self.label_to_dev(label)
        if partition_or_disk is None:
            return None

        if os.path.exists(os.path.join('/sys/class/block', partition_or_disk, 'partition')):
            return self.get_disk_from_partition(partition_or_disk)
        else:
            return partition_or_disk

    @private
    def get_disk_from_partition(self, part_name):
        if not os.path.exists(os.path.join('/dev', part_name)):
            return None
        try:
            with open(os.path.join('/sys/class/block', part_name, 'partition'), 'r') as f:
                part_num = f.read().strip()
        except FileNotFoundError:
            return part_name
        else:
            if part_name.startswith(('nvme', 'pmem')):
                # nvme/pmem partitions would be like nvmen1p1 where disk is nvmen1
                part_num = f'p{part_num}'
        return part_name.rsplit(part_num, 1)[0].strip()

    @private
    def get_partition_for_disk(self, disk, partition):
        if disk.startswith(('nvme', 'pmem')):
            # FIXME: This is a hack for nvme/pmem disks, however let's please come up with a better way
            # to link disks with their partitions
            return f'{disk}p{partition}'
        else:
            return f'{disk}{partition}'
