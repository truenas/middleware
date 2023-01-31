import multiprocessing

from pyudev import Context

from middlewared.service import Service, accepts, job
from middlewared.schema import List, Str
from middlewared.plugins.disk_.enums import DISKS_TO_IGNORE
from middlewared.plugins.device_.device_info import RE_NVME_PRIV


def taste_it(disk):
    try:
        with open(disk, 'wb'):
            return
    except Exception:
        pass


def retaste_disks_impl(disks: set = None):
    if disks is None:
        disks = set()
        for disk in Context().list_devices(subsystem='block', DEVTYPE='disk'):
            if disk.sys_name.startswith(DISKS_TO_IGNORE) or RE_NVME_PRIV.match(disk.sys_name):
                continue
            disks.add(f'/dev/{disk.sys_name}')

    with multiprocessing.Pool() as p:
        # we use processes so that these operations are truly
        # "parrallel" (side-step the GIL) since we have systems
        # with 1k+ disks. Since this runs, potentially, on failover
        # event we need to squeeze out every bit of perf we can get
        p.map(taste_it, disks)


class DiskService(Service):

    @accepts(List('disks', required=False, default=None, items=[Str('name', required=True)]))
    @job(lock='disk_retaste')
    def retaste(self, job, disks):
        if disks:
            # remove duplicates and prefix '/dev' (i.e. /dev/sda, /dev/sdb, etc)
            disks = set(f'/dev/{i.removeprefix("/dev/")}' for i in disks)

        job.set_progress(85, 'Retasting disks')
        retaste_disks_impl(disks)

        job.set_progress(100, 'Retasting disks done')
        return 'SUCCESS'
