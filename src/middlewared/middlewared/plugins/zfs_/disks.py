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
            if dev.sys_name.startswith('sr') or dev.properties['DEVTYPE'] not in ('disk', 'partition'):
                continue

            # this is "sda/sda1/sda2/sda3" etc
            sys_devices[dev.sys_name] = dev.sys_name

            # this is the various "disk/by-partuuid" or "disk/by-label" or "disk/by-id" etc
            for link in (dev.properties['DEVLINKS'] or '').split():
                sys_devices[link.removeprefix('/dev/')] = dev.sys_name

        mapping = {name: set()}
        for disk in self.middleware.call_sync('zfs.pool.get_devices', name):
            try:
                mapping[name].add(sys_devices[disk])
            except KeyError:
                continue

        return list(mapping[name])
