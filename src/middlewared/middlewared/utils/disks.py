import pathlib
import re
import typing

import pyudev


RE_IS_PART = re.compile(r'p\d{1,3}$')


def safe_retrieval(prop, key, default, as_int=False) -> typing.Any:
    value = prop.get(key)
    if value is not None:
        if type(value) == bytes:
            value = value.strip().decode()
        else:
            value = value.strip()
        return value if not as_int else int(value)

    return default


def get_disk_serial_from_block_device(block_device: pyudev.Device) -> str:
    return (
        safe_retrieval(block_device.properties, 'ID_SCSI_SERIAL', '') or
        safe_retrieval(block_device.properties, 'ID_SERIAL_SHORT', '') or
        safe_retrieval(block_device.properties, 'ID_SERIAL', '')
    )


def valid_zfs_partition_uuids():
    # https://salsa.debian.org/debian/gdisk/blob/master/parttypes.cc for valid zfs types
    # 516e7cba was being used by freebsd and 6a898cc3 is being used by linux
    return (
        '6a898cc3-1dd2-11b2-99a6-080020736631',
        '516e7cba-6ecf-11d6-8ff8-00022d09712b',
    )


def dev_to_ident(name, sys_disks):
    """Map a disk device (i.e. sda5) to its respective "identifier"
    (i.e. "{serial_lunid}AAAA_012345")"""
    try:
        dev = sys_disks[name]
    except KeyError:
        return ''
    else:
        if dev['serial_lunid']:
            return f'{{serial_lunid}}{dev["serial_lunid"]}'
        elif dev['serial']:
            return f'{{serial}}{dev["serial"]}'
        elif dev['parts']:
            for part in filter(lambda x: x['partition_type'] in valid_zfs_partition_uuids(), dev['parts']):
                return f'{{uuid}}{part["partition_uuid"]}'

    return f'{{devicename}}{name}'


def get_disk_names() -> list[str]:
    """
    NOTE: The return of this method should match the keys retrieve when running `self.get_disks`.
    """
    disks = []
    try:
        for disk in pathlib.Path('/sys/class/block').iterdir():
            if not disk.name.startswith(('sd', 'nvme', 'pmem')):
                continue
            elif RE_IS_PART.search(disk.name):
                # sdap1/nvme0n1p12/pmem0p1/etc
                continue
            elif disk.name[:2] == 'sd' and disk.name[-1].isdigit():
                # sda1/sda2/etc
                continue
            else:
                disks.append(disk.name)
    except FileNotFoundError:
        pass

    return disks


def get_disks_with_identifiers() -> dict[str, str]:
    disks = {}
    context = pyudev.Context()
    for disk_name in get_disk_names():
        try:
            # Retrieve the device directly by name
            block_device = pyudev.Devices.from_name(context, 'block', disk_name)
            serial = get_disk_serial_from_block_device(block_device)
            lunid = safe_retrieval(block_device.properties, 'ID_WWN', '').removeprefix('0x').removeprefix('eui.')
            parts = []
            for partition in filter(
                lambda p: all(p.get(k) for k in ('ID_PART_ENTRY_TYPE', 'ID_PART_ENTRY_UUID')), block_device.children
            ):
                parts.append({
                    'partition_type': partition['ID_PART_ENTRY_TYPE'],
                    'partition_uuid': partition['ID_PART_ENTRY_UUID'],
                })
        except pyudev.DeviceNotFoundError:
            block_device_data = {
                'serial': '',
                'lunid': '',
                'serial_lunid': '',
                'parts': [],
            }
        else:
            block_device_data = {
                'serial': serial,
                'lunid': lunid or None,
                'serial_lunid': f'{serial}_{lunid}' if serial and lunid else None,
                'parts': parts,
            }
        disks[disk_name] = dev_to_ident(disk_name, {disk_name: block_device_data})

    return disks
