import fcntl
import logging
import multiprocessing
import os
import re

from middlewared.schema import List, Str
from middlewared.service import Service, accepts, job, private


logger = logging.getLogger(__name__)

SD_PATTERN = re.compile(r"^sd[a-z]+$")
NVME_PATTERN = re.compile(r"^nvme\d+n\d+$")


def taste_it(disk, errors):
    BLKRRPART = 0x125f  # force reread partition table

    fd = None
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
        if fd is not None:
            os.close(fd)


def retaste_disks_impl(disks: set = None):
    if disks is None:
        disks = set()
        with os.scandir('/dev') as sdir:
            for i in sdir:
                if SD_PATTERN.match(i.name) or NVME_PATTERN.match(i.name):
                    disks.add(i.path)

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

    @private
    def update_partition_table_quick(self, devnode):
        """
        Call the BLKRRPATH ioctl to update the partition table on a single dev node
        Used by 'wipe'
        """
        errors = {}
        taste_it(devnode, errors)
        return errors

    @accepts(List('disks', required=False, default=None, items=[Str('name', required=True)]))
    @job(lock='disk_retaste', lock_queue_size=1)
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
