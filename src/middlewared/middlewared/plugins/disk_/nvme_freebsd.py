from os.path import exists

from nvme import get_nsid
from middlewared.service import private, Service


class DiskService(Service):

    @private
    def nvme_to_nvd_map(self, ignore_boot_disks=False):
        nvme_to_nvd = {}
        boot_disks = self.middleware.call_sync('boot.get_disks') if ignore_boot_disks else []
        for disk in self.middleware.call_sync('disk.query', [['devname', '^', 'nvd']]):
            if disk['devname'] in boot_disks:
                continue

            try:
                n = int(disk['devname'][len('nvd'):])
            except ValueError:
                continue

            nvd = f'/dev/{disk["devname"]}'
            if not exists(nvd):
                continue

            nvme = get_nsid(nvd)
            if nvme:
                nvme_to_nvd[int(nvme[4:])] = n

        return nvme_to_nvd
