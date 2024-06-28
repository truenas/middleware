import collections
import contextlib
import glob
import os
import pathlib

import pyudev

from middlewared.service import CallError, private, Service


# The basic unit of a block I/O is a sector. A sector is
# 512 (2 ** 9) bytes. In sysfs, the files (sector_t type)
# `<disk>/<part>/start` and `<disk>/<part>/size` are
# shown as a multiple of 512 bytes. Most user-space
# tools (fdisk, parted, sfdisk, etc) treat the partition
# offsets in sectors.
BYTES_512 = 512
PART_INFO_FIELDS = (
    # queue/logical_block_size (reported as a multiple of BYTES_512)
    'lbs',
    # starting offset of partition in sectors
    'start_sector',
    # ending offset of partition in sectors
    'end_sector',
    # total partition size in sectors
    'total_sectors',
    # starting offset of partition in bytes
    'start_byte',
    # ending offset of partition in bytes
    'end_byte',
    # total size of partition in bytes
    'total_bytes',
)
PART_INFO = collections.namedtuple('part_info', PART_INFO_FIELDS, defaults=(0,) * len(PART_INFO_FIELDS))


def get_partition_size_info(disk_name, s_offset, s_size):
    """Kernel sysfs reports most disk files related to "size" in 512 bytes.
    To properly calculate the starting SECTOR of partitions, you must
    look at logical_block_size (again, reported in 512 bytes) and
    do some calculations. It is _very_ important to do this properly
    since almost all userspace tools that format disks expect partition
    positions to be in sectors."""
    lbs = 0
    with contextlib.suppress(FileNotFoundError, ValueError):
        with open(f'/sys/block/{disk_name}/queue/logical_block_size') as f:
            lbs = int(f.read().strip())

    if not lbs:
        # this should never happen
        return PART_INFO()

    # important when dealing with 4kn drives
    divisor = lbs // BYTES_512
    # sectors
    start_sector = s_offset // divisor
    total_sectors = s_size // divisor
    end_sector = total_sectors + start_sector - 1
    # bytes
    start_byte = start_sector * lbs
    end_byte = end_sector * lbs
    total_bytes = total_sectors * lbs

    return PART_INFO(*(
        lbs, start_sector, end_sector, total_sectors,
        start_byte, end_byte, total_bytes,
    ))


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

        return dev.attributes.asint('size') * BYTES_512

    @private
    def list_partitions(self, disk):
        parts = []
        try:
            bd = pyudev.Devices.from_name(pyudev.Context(), 'block', disk)
        except pyudev.DeviceNotFoundByNameError:
            return parts

        if not bd.children:
            return parts

        req_keys = ('ID_PART_ENTRY_' + i for i in ('TYPE', 'UUID', 'NUMBER', 'SIZE'))
        for p in filter(lambda p: all(p.get(k) for k in req_keys), bd.children):
            part_name = self.get_partition_for_disk(disk, p['ID_PART_ENTRY_NUMBER'])
            pinfo = get_partition_size_info(disk, int(p['ID_PART_ENTRY_OFFSET']), int(p['ID_PART_ENTRY_SIZE']))
            part = {
                'name': part_name,
                'partition_type': p['ID_PART_ENTRY_TYPE'],
                'partition_number': int(p['ID_PART_ENTRY_NUMBER']),
                'partition_uuid': p['ID_PART_ENTRY_UUID'],
                'disk': disk,
                'start_sector': pinfo.start_sector,
                'start': pinfo.start_byte,
                'end_sector': pinfo.end_sector,
                'end': pinfo.end_byte,
                'size': pinfo.total_bytes,
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
