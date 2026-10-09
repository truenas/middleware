from concurrent.futures import ThreadPoolExecutor
import errno
import fcntl
import logging
import os

from middlewared.service import Service, job, private
from middlewared.utils.disks_.disk_class import iterate_disks

logger = logging.getLogger(__name__)


def taste_it(disk):
    BLKRRPART = 0x125f  # force reread partition table

    try:
        fd = os.open(disk, os.O_WRONLY)
        try:
            fcntl.ioctl(fd, BLKRRPART)
        finally:
            os.close(fd)
    except OSError as e:
        # EBUSY means the disk is in use, so the kernel will not
        # reread its partition table. That is expected, not a failure.
        if e.errno != errno.EBUSY:
            logger.error('%s: failed to retaste disk: %s', disk, e)


def retaste_disks_impl(disk_serials: set = None):
    if disk_serials is None:
        disks = {i.devpath for i in iterate_disks()}
    else:
        disks = set()
        for i in filter(lambda x: x.serial in disk_serials, iterate_disks()):
            disks.add(i.devpath)

    # Retasting is two blocking system calls per disk and both release
    # the GIL, so threads run them in parallel. We have systems with 1k+
    # disks and this runs, potentially, on failover event, hence more
    # threads than the default (they only wait on the kernel).
    with ThreadPoolExecutor(max_workers=64) as executor:
        list(executor.map(taste_it, disks))


class DiskService(Service):

    @private
    @job(lock='disk_retaste', lock_queue_size=1)
    def retaste(self, job, disks_serials: list[str] | None = None):
        job.set_progress(85, 'Retasting disks')
        retaste_disks_impl(disks_serials)

        job.set_progress(95, 'Waiting for disk events to settle')
        self.middleware.call_sync('device.settle_udev_events')

        job.set_progress(100, 'Retasting disks done')
        return 'SUCCESS'
