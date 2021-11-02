from libzfs import ZFS
from middlewared.service import Service


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def get_disks(self, name):
        try:
            with ZFS() as zfs:
                disks = [i.replace('/dev/', '').replace('.eli', '') for i in zfs.get(name).disks]
        except Exception:
            self.logger.error('Failed to retrieve disks for %r', name, exc_info=True)
            return []

        pool_disks = []
        info = self.middleware.call_sync('disk.label_to_dev_and_disk')
        for disk in disks:
            found_disk = None
            found_label = info['label_to_dev'].get(disk)
            if found_label:
                found_disk = info['dev_to_disk'].get(found_label)
            else:
                # maybe the disk for thi zpool doesn't have a label (freenas-boot/boot-pool)
                # we still need to try and find the raw disk
                found_disk = info['dev_to_disk'].get(disk)

            pool_disks.append(found_disk) if found_disk else None

        return pool_disks
