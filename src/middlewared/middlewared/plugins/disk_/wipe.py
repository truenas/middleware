import asyncio
import os
import pathlib
import threading
import time

from middlewared.schema import accepts, Bool, Ref, Str, returns
from middlewared.service import job, Service, private


CHUNK = 1048576  # 1MB binary
# Maximum number of attempts to request partition table update
MAX_NUM_PARTITION_UPDATE_RETRIES = 4


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
        path_obj = pathlib.path(f"/sys/block/{dev_name}")
        for _try in range(tries):
            if startsect:
                # dictionary of partition info has already been populated
                # so we'll break out early
                return startsect
            else:
                time.sleep(0.2)

            try:
                sectsize = int((path_obj / 'queue/logical_block_size').read_text().strip())
                with os.scandir(path_obj) as dir_contents:
                    for partdir in filter(lambda x: x.is_dir() and x.name.startswith(dev_name), dir_contents):
                        part_num = int((partdir / 'partition').read_text().strip())
                        part_start = int((partdir / 'start').read_text().strip()) * sectsize
                        startsect[part_num] = part_start
            except (FileNotFoundError, ValueError):
                continue
            except Exception:
                if _try == retries:
                    self.logger.error('Unexpected failure gathering partition info', exc_info=True)

        return startsect

    def _wipe_impl(self, job, dev, mode, event):
        disk_path = f'/dev/{dev}'
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
                to_write = bytearray(CHUNK).zfill(0)
            else:
                to_write = bytearray(os.urandom(CHUNK))

            # seek back to the beginning of the disk
            os.lseek(f.fileno(), 0, os.SEEK_SET)

            if mode == 'QUICK':
                # Get partition info before it gets destroyed
                try:
                    disk_parts = self.get_partitions_quick(dev)
                except Exception:
                    disk_parts = {}

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

                # The middle partitions often contain old cruft.  Clean those.
                if len(disk_parts) > 1:
                    _30MiB = 30 * CHUNK
                    _30MiB_from_end = size - _30MiB
                    for sector_start in disk_parts.values():
                        # Skip any that start under 30 MiB or 30MiB from the end
                        if (sector_start < _30MiB) or (_30MiB_from_end < sector_start):
                            continue

                        # Start 2 MiB back from the start and 'clean' 2 MiB past, 4 MiB total
                        os.lseek(f.fileno(), sector_start - (2 * CHUNK), os.SEEK_SET)
                        for i in range(4):
                            os.write(f.fileno(), to_write)
                            os.fsync(f.fileno())
                            if event.is_set():
                                return
                    # This is quick. We can reasonably skip the progress update

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

        # The call to update_partition_table_quick can require retries
        error = {}
        retries = MAX_NUM_PARTITION_UPDATE_RETRIES
        # Unfortunately, without a small initial sleep, the following
        # retry loop will almost certainly require two iterations.
        time.sleep(0.1)
        while retries > 0:
            # Use BLKRRPATH ioctl to update the kernel partition table
            error = self.middleware.call_sync('disk.update_partition_table_quick', disk_path)
            if not error[disk_path]:
                break
            time.sleep(0.1)
            retries -= 1

        if error[disk_path]:
            self.logger.error('Error partition table update "%s": %s', disk_path, error[disk_path])

    @accepts(
        Str('dev'),
        Str('mode', enum=['QUICK', 'FULL', 'FULL_RANDOM'], required=True),
        Bool('synccache', default=True),
        Ref('swap_removal_options'),
    )
    @returns()
    @job(
        lock=lambda args: args[0],
        description=lambda dev, mode, *args: f'{mode.replace("_", " ").title()} wipe of disk {dev}',
        abortable=True,
    )
    async def wipe(self, job, dev, mode, sync, options):
        """
        Performs a wipe of a disk `dev`.
        It can be of the following modes:
          - QUICK: clean the first and last 32 megabytes on `dev`
          - FULL: write whole disk with zero's
          - FULL_RANDOM: write whole disk with random bytes
        """
        await self.middleware.call('disk.swaps_remove_disks', [dev], options)
        event = threading.Event()
        try:
            await self.middleware.run_in_thread(self._wipe_impl, job, dev, mode, event)
        except asyncio.CancelledError:
            event.set()
            raise
        if sync:
            await self.middleware.call('disk.sync', dev)
