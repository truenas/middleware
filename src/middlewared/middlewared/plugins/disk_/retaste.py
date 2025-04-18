import fcntl
import logging
import multiprocessing
import os

from middlewared.service import Service, job, private
from middlewared.utils.disks_.disk_class import iterate_disks

logger = logging.getLogger(__name__)


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


def retaste_disks_impl(disk_serials: set = None):
    if disk_serials is None:
        disks = {i.devpath for i in iterate_disks()}
    else:
        disks = set()
        for i in filter(lambda x: x.serial in disk_serials, iterate_disks()):
            disks.add(i.devpath)

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

    @private
    @job(lock='disk_retaste', lock_queue_size=1)
    def retaste(self, job, disks_serials: list[str] | None = None):
        job.set_progress(85, 'Retasting disks')
        retaste_disks_impl(disks_serials)

        job.set_progress(95, 'Waiting for disk events to settle')
        self.middleware.call_sync('device.settle_udev_events')

        job.set_progress(100, 'Retasting disks done')
        return 'SUCCESS'
