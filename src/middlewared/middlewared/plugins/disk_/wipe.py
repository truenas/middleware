import asyncio
import os
import pathlib
import threading
import time

from middlewared.api import api_method
from middlewared.api.current import DiskWipeArgs, DiskWipeResult
from middlewared.service import job, Service, private


CHUNK = 1048576  # 1MB binary


class DiskService(Service):

    @private
    def get_partitions_quick(self, dev_name, tries=None):
        """
        Lightweight function to generate a dictionary of
        partition start in units of bytes.

        `tries` int, specifies the number of tries that we will
            look for the various files in sysfs. Often times this
            function is called after a drive has been formatted
            and so the caller might want to wait on udev to become
            aware of the new partitions.
        """
        if tries in (0, 1) or not isinstance(tries, int):
            tries = 1
        else:
            tries = min(tries, 10)

        startsect = {}
        sectsize = 0
        path_obj = pathlib.Path(f"/sys/block/{dev_name}")
        for _try in range(tries):
            if startsect:
                # dictionary of partition info has already been populated
                # so we'll break out early
                return startsect
            else:
                time.sleep(0.5)

            try:
                sectsize = int((path_obj / 'queue/logical_block_size').read_text().strip())
                with os.scandir(path_obj) as dir_contents:
                    for partdir in filter(lambda x: x.is_dir() and x.name.startswith(dev_name), dir_contents):
                        partdir_obj = pathlib.Path(partdir.path)
                        part_num = int((partdir_obj / 'partition').read_text().strip())
                        part_start = int((partdir_obj / 'start').read_text().strip()) * sectsize
                        startsect[part_num] = part_start
            except (FileNotFoundError, ValueError):
                continue
            except Exception:
                if _try + 1 == tries:  # range() built-in is half-open
                    self.logger.error('Unexpected failure gathering partition info', exc_info=True)

        return startsect

    def _wipe_impl(self, job, dev, mode, event):
        disk_path = f'/dev/{dev.removeprefix("/dev/")}'
        with open(os.open(disk_path, os.O_WRONLY | os.O_EXCL), 'wb') as f:
            size = os.lseek(f.fileno(), 0, os.SEEK_END)
            if size == 0:
                # no size means nothing else will work
                self.logger.error('Unable to determine size of "%s"', dev)
                return
            elif size < 33554432 and mode == 'QUICK':
                # we wipe the first and last 33554432 bytes (32MB) of the
                # device when it's the "QUICK" mode so if the device is smaller
                # than that, ignore it.
                return

            # no reason to write more than 1MB at a time
            # or kernel will break them into smaller chunks
            if mode in ('QUICK', 'FULL'):
                to_write = b'\0' * CHUNK
            else:
                to_write = os.urandom(CHUNK)

            # seek back to the beginning of the disk
            os.lseek(f.fileno(), 0, os.SEEK_SET)

            if mode == 'QUICK':
                _32 = 32
                for i in range(_32):
                    # wipe first 32MB
                    os.write(f.fileno(), to_write)
                    os.fsync(f.fileno())
                    if event.is_set():
                        return
                    # we * 50 since we write a total of 64MB
                    # so this will be 50% of the total
                    job.set_progress(round(((i / _32) * 50), 2))

                # seek to 32MB before end of drive
                os.lseek(f.fileno(), (size - (CHUNK * _32)), os.SEEK_SET)
                _64 = _32 * 2
                for i in range(_32, _64):  # this is done to have accurate reporting
                    # wipe last 32MB
                    os.write(f.fileno(), to_write)
                    os.fsync(f.fileno())
                    if event.is_set():
                        return
                    job.set_progress(round(((i / _64) * 100), 2))
            else:
                iterations = (size // CHUNK)
                for i in range(iterations):
                    os.write(f.fileno(), to_write)
                    # Linux allocates extremely large buffers for some disks. Even after everything is written and the
                    # device is successfully closed, disk activity might still continue for quite a while. This will
                    # give a false sense of data on the disk being completely destroyed while in reality it is still
                    # not.
                    # Additionally, such a behavior causes issues when aborting the disk wipe. Even after the file
                    # descriptor is closed, OS will prevent any other program from opening the disk with O_EXCL until
                    # all the buffers are flushed, resulting in a "Device or resource busy" error.
                    os.fsync(f.fileno())
                    if event.is_set():
                        return
                    job.set_progress(round(((i / iterations) * 100), 2))

    @api_method(
        DiskWipeArgs,
        DiskWipeResult,
        audit="Disk Wipe",
        roles=["DISK_WRITE"],
    )
    @job(
        lock=lambda args: args[0],
        description=lambda dev, mode, *args: f'{mode.replace("_", " ").title()} wipe of disk {dev}',
        abortable=True,
    )
    async def wipe(self, job, dev, mode, sync):
        """Performs a wipe of a disk `dev`."""
        event = threading.Event()
        try:
            await self.middleware.run_in_thread(self._wipe_impl, job, dev, mode, event)
        except asyncio.CancelledError:
            event.set()
            raise
        if sync:
            await self.middleware.call('disk.sync', dev)
