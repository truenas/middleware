import collections
from collections.abc import Generator
import contextlib
import os
import pathlib
import time

import pyudev

from middlewared.service import CallError, private, Service
from middlewared.utils.disks_.disk_class import DiskEntry, iterate_disks

from .gpt_utils import read_gpt_partitions

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
        raise RuntimeError(f"Logical block size did not exist for disk {disk_name}")

    # important when dealing with 4kn drives
    divisor = lbs // BYTES_512
    # sectors
    start_sector = s_offset // divisor
    total_sectors = s_size // divisor
    end_sector = total_sectors + start_sector - 1
    # bytes
    start_byte = start_sector * lbs
    end_byte = (end_sector * lbs) + lbs - 1
    total_bytes = total_sectors * lbs

    return PART_INFO(*(
        lbs, start_sector, end_sector, total_sectors,
        start_byte, end_byte, total_bytes,
    ))


class DiskService(Service):

    @private
    def get_disks(self, name_filters: list[str] | None = None) -> Generator[DiskEntry]:
        """
        Iterate over /dev and yield a `DiskEntry` object for
        each disk detected on the system.

        Args:
            name_filters: list of strings, represent a list
                of disk names that will be filtered upon.
                The name of the disk may take the form
                of 'sda' or '/dev/sda'.
        """
        if name_filters is None:
            for disk in iterate_disks():
                yield disk
        else:
            for disk in iterate_disks():
                if disk.name in name_filters or disk.devpath in name_filters:
                    yield disk

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
    def get_part_uuid_from_udev(self, disk, part_type):
        try:
            bd = pyudev.Devices.from_name(pyudev.Context(), 'block', disk)
            for i in bd.children:
                if (pguid := i.get('ID_PART_ENTRY_UUID')) and (tguid := i.get('ID_PART_ENTRY_TYPE')):
                    if tguid == part_type:
                        return pguid
        except pyudev.DeviceNotFoundByNameError:
            raise CallError(f'Disk {disk!r} not found!')

    @private
    def gptid_from_part_type(self, disk, part_type, retries=10, sleep_time=0.5):
        # max time to sleep and retry is 10 * 6.0 (60 seconds)
        # if a drive is taking longer than that to bubble
        # up partition information, we have other problems
        retries = max(min(retries, 10), 2)
        sleep_time = max(min(sleep_time, 6.0), 0.2)
        part_entry_guid_on_disk = None
        for i in filter(lambda x: x.part_type_guid == part_type, read_gpt_partitions(disk)):
            # Let's read directly from the disk to see if there is a
            # partition on it.
            part_entry_guid_on_disk = i.part_entry_guid
            break

        do_retry = False
        part = self.get_part_uuid_from_udev(disk, part_type)
        if not part:
            if part_entry_guid_on_disk:
                # udevd's miserable design is built-around the ridiculous
                # notion of symlinks and just willy-nilly removing/re-adding
                # them for seemingly no good reason. (i.e. just open
                # a disk with a gpt parition on it in write mode and close it)
                # For whatever reason, that generates a remove event so the
                # symlink gets torn-down and re-added. Most of the time, this
                # happens in 100th's of a single second. Sometimes, again randomly,
                # this takes many seconds. When it takes many seconds and we're
                # depending on that symlink to exist for ZFS, it's a race condition
                # which ultimately leads to formatting the drive successfully, but
                # failing to create the zpool because the symlink pointing to the
                # block device node doesn't exist at that specific time.
                # SO, if we're at this point it means the block device really has
                # a GPT partition on it and it matches what we expect but the udevd
                # cache has been looked at incorrectly and has decided to remove it.
                # We'll just retry a few times here and hope the sun doesn't have
                # too strong of a solar flare and cause udevd to run off and do dumb
                # things.
                do_retry = True
            else:
                # maybe someone called this on a drive with no GPT partitions
                raise CallError(f'Partition type {part_type} not found on {disk}')

        if do_retry:
            for i in range(retries):
                if part := self.get_part_uuid_from_udev(disk, part_type):
                    return f'disk/by-partuuid/{part}'
                else:
                    time.sleep(sleep_time)

            if part_entry_guid_on_disk:
                return f'disk/by-partuuid/{part_entry_guid_on_disk}'

            total_wait = retries * sleep_time
            raise CallError(f'Partition type {part_type} not found on {disk} after waiting {total_wait} seconds')

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
