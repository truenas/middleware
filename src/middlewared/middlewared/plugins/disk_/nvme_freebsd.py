import os

from nvme import get_nsid

from middlewared.service import private, Service


class DiskService(Service):

    @private
    def nvme_to_nvd_map(self):
        nvme_to_nvd = {}
        for disk in self.middleware.call_sync("disk.query", [["devname", "^", "nvd"]]):
            try:
                n = int(disk["devname"][len("nvd"):])
            except ValueError:
                continue
            nvd = f"/dev/{disk['devname']}"
            if not os.path.exists(nvd):
                continue
            nvme = get_nsid(nvd)
            if nvme is not None:
                nvme_to_nvd[int(nvme[4:])] = n

        return nvme_to_nvd
