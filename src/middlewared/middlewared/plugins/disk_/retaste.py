import fcntl
import logging
import multiprocessing
import os

from pyudev import Context

from middlewared.service import Service, accepts, job
from middlewared.schema import List, Str
from middlewared.plugins.disk_.enums import DISKS_TO_IGNORE
from middlewared.plugins.device_.device_info import RE_NVME_PRIV

logger = logging.getLogger(__name__)


def taste_it(disk, errors):
    BLKRRPART = 0x125f  # force reread partition table

    errors[disk] = []
    try:
        fd = os.open(disk, os.O_WRONLY)
    except Exception as e:
        errors[disk].append(str(e))
        # can't open, no reason to continue
    else:
        try:
            fcntl.ioctl(fd, BLKRRPART)
        except Exception as e:
            errors[disk].append(str(e))
    finally:
        os.close(fd)


def retaste_disks_impl(disks: set = None):
    if disks is None:
        disks = set()
        for disk in Context().list_devices(subsystem='block', DEVTYPE='disk'):
            if disk.sys_name.startswith(DISKS_TO_IGNORE) or RE_NVME_PRIV.match(disk.sys_name):
                continue
            disks.add(f'/dev/{disk.sys_name}')

    with multiprocessing.Manager() as m:
        errors = m.dict()
        with multiprocessing.Pool() as p:
            # we use processes so that these operations are truly
            # "parrallel" (side-step the GIL) since we have systems
            # with 1k+ disks. Since this runs, potentially, on failover
            # event we need to squeeze out every bit of perf we can get
            p.starmap(taste_it, [(disk, errors) for disk in disks])

        for disk, errors in filter(lambda x: len(x[1]) > 0, errors.items()):
            logger.error('Failed to retaste %r with error(s): %s', disk, ', '.join(errors))

    del errors


class DiskService(Service):

    @accepts(List('disks', required=False, default=None, items=[Str('name', required=True)]))
    @job(lock='disk_retaste')
    def retaste(self, job, disks):
        if disks:
            # remove duplicates and prefix '/dev' (i.e. /dev/sda, /dev/sdb, etc)
            disks = set(f'/dev/{i.removeprefix("/dev/")}' for i in disks)

        job.set_progress(85, 'Retasting disks')
        retaste_disks_impl(disks)

        job.set_progress(95, 'Waiting for disk events to settle')
        self.middleware.call_sync('device.settle_udev_events')

        job.set_progress(100, 'Retasting disks done')
        return 'SUCCESS'
