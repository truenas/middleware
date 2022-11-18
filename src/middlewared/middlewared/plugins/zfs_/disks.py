import pyudev

from middlewared.service import Service


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def get_disks(self, name):
        sys_devices = {}
        for dev in pyudev.Context().list_devices(subsystem='block'):
            if dev.sys_name.startswith('sr'):
                continue

            devtype = dev.properties.get('DEVTYPE', '')
            if not devtype or devtype not in ('disk', 'partition'):
                continue

            # this is "sda/sda1/sda2/sda3" etc
            sys_devices[dev.sys_name] = dev.sys_name

            # zpool could have been created using the raw partition
            # (i.e. "sda3"). This happens on the "boot-pool" for example.
            # We need to get the parent device name when this occurs.
            if dev.sys_number and (parent := dev.find_parent('block')):
                sys_devices[dev.sys_name] = parent.sys_name

            # these are the the various by-{partuuid/label/id/path} etc labels
            if dev.properties['DEVTYPE'] == 'partition':
                for link in (dev.properties.get('DEVLINKS') or '').split():
                    sys_devices[link.removeprefix('/dev/')] = dev.find_parent('block').sys_name

        mapping = {name: set()}
        for disk in self.middleware.call_sync('zfs.pool.get_devices', name):
            try:
                mapping[name].add(sys_devices[disk])
            except KeyError:
                continue

        return list(mapping[name])
