from middlewared.plugins.zfs_.utils import zvol_name_to_path


ACTIVE_STATES = ['RUNNING', 'SUSPENDED']
LIBVIRT_USER = 'libvirt-qemu'
NGINX_PREFIX = '/vm/display'


def disk_uniqueness_integrity_check(device: dict, instance: dict):
    # This ensures that the disk is not already present for `instance`
    def translate_device(dev):
        # A disk should have a path configured at all times, when that is not the case, that means `dtype` is DISK
        # and end user wants to create a new zvol in this case.
        return dev['attributes'].get('path') or zvol_name_to_path(dev['attributes']['zvol_name'])

    disks = [
        d for d in instance['devices']
        if d['attributes']['dtype'] in ('DISK', 'RAW', 'CDROM') and translate_device(d) == translate_device(device)
    ]
    if not disks:
        # We don't have that disk path in instance devices, we are good to go
        return True
    elif len(disks) > 1:
        # instance is mis-configured
        return False
    elif not device.get('id') and disks:
        # A new device is being created, however it already exists in instance. This can also happen when instance
        # is being created, in that case it's okay. Key here is that we won't have the id field present
        return not bool(disks[0].get('id'))
    elif device.get('id'):
        # The device is being updated, if the device is same as we have in db, we are okay
        return device['id'] == disks[0].get('id')
    else:
        return False
