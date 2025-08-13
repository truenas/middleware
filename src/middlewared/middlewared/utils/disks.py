import os
import re

import pyudev


DISKS_TO_IGNORE = ('sr', 'md', 'dm-', 'loop', 'zd')
RE_IS_PART = re.compile(r'p\d{1,3}$')
# sda, vda, xvda, nvme0n1 but not sda1/vda1/xvda1/nvme0n1p1
VALID_WHOLE_DISK = re.compile(r'^sd[a-z]+$|^vd[a-z]+$|^xvd[a-z]+$|^nvme\d+n\d+$')


def safe_retrieval(prop, key, default, as_int=False):
    value = prop.get(key)
    if value is not None:
        if isinstance(value, bytes):
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
        elif dev.get('parts'):
            for part in filter(lambda x: x['partition_type'] in valid_zfs_partition_uuids(), dev['parts']):
                return f'{{uuid}}{part["partition_uuid"]}'

    return f'{{devicename}}{name}'


def get_disk_names() -> list[str]:
    """
    NOTE: The return of this method should match the keys retrieve when running `self.get_disks`.
    """
    disks = []
    with os.scandir('/dev') as sdir:
        for i in filter(lambda x: VALID_WHOLE_DISK.match(x.name), sdir):
            disks.append(i.name)
    return disks


def get_disks_with_identifiers(
    disks_identifier_required: list[str] | None = None, block_devices_data: dict[str, dict] | None = None,
) -> dict[str, str]:
    disks = {}
    available_disks = get_disk_names()
    disks_identifier_required = disks_identifier_required or available_disks
    block_devices_data = block_devices_data or {}
    context = pyudev.Context()
    for disk_name in disks_identifier_required:
        if disk_name not in available_disks:
            continue

        if block_device_data := block_devices_data.get(disk_name, {}):
            identifier = dev_to_ident(disk_name, block_devices_data)
            if not identifier.startswith('{devicename}'):
                disks[disk_name] = identifier
                continue

        # If we had cached data but we still end up here, it means we still need to try the partitions check
        # and see if we can use that as an identifier
        try:
            # Retrieve the device directly by name
            block_device = pyudev.Devices.from_name(context, 'block', disk_name)
            if block_device_data:
                serial, lunid = block_device_data['serial'], block_device_data['lunid']
            else:
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
            } | block_device_data
        else:
            block_device_data = {
                'serial': serial,
                'lunid': lunid or None,
                'serial_lunid': f'{serial}_{lunid}' if serial and lunid else None,
                'parts': parts,
            }

        disks[disk_name] = dev_to_ident(disk_name, {disk_name: block_device_data})

    return disks
