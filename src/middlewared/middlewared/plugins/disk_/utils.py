def valid_zfs_partition_uuids():
    # https://salsa.debian.org/debian/gdisk/blob/master/parttypes.cc for valid zfs types
    # 516e7cba was being used by freebsd and 6a898cc3 is being used by linux
    return (
        '6a898cc3-1dd2-11b2-99a6-080020736631',
        '516e7cba-6ecf-11d6-8ff8-00022d09712b',
    )


def dev_to_ident(name, sys_disks, uuids):
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
            for part in filter(lambda x: x['partition_type'] in uuids, dev['parts']):
                return f'{{uuid}}{part["partition_uuid"]}'

    return f'{{devicename}}{name}'
