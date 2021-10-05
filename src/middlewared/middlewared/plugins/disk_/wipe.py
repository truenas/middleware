import os

from bsd.disk import get_size_with_file
from middlewared.schema import accepts, Bool, Ref, Str
from middlewared.service import job, private, Service


CHUNK = 1048576  # 1MB binary


class DiskService(Service):

    @private
    def _wipe(self, data):
        with open(f'/dev/{data["dev"]}', 'wb') as f:
            try:
                size = get_size_with_file(f)
                if size == 0:
                    # make sure to log something
                    self.logger.error('Reported size of %r is 0', f.name)
            except Exception:
                self.logger.error('Failed to determine size of %r', f.name, exc_info=True)
                size = None

            if not size or (size < 33554432 and data['mode'] == 'QUICK'):
                # no size means nothing else will work or we wipe
                # the first and last 33554432 bytes (32MB) of the
                # device when it's the "QUICK" mode so if the
                # device is smaller than that, ignore it.
                return

            # seek to the beginning of the disk to be safe
            os.lseek(f.fileno(), os.SEEK_SET, os.SEEK_SET)

            # freeBSD 12+ changed maxphys to 1MB so if we try
            # to write more than that at any given time then
            # it gets chunked behind the scenes. This also allows
            # us to save ram usage by only allocating a 1MB buffer
            if data['mode'] in ('QUICK', 'FULL'):
                to_write = bytearray(CHUNK).zfill(0)
            else:
                to_write = bytearray(os.urandom(CHUNK))

            if data['mode'] == 'QUICK':
                _32 = 32
                for i in range(_32):
                    # wipe first 32MB
                    os.write(f.fileno(), to_write)
                    os.fsync(f.filno())

                # seek to 32MB before end of drive
                os.lseek(f.fileno(), (size - (CHUNK * _32)), os.SEEK_SET)
                for i in range(_32):
                    # wipe last 32MB
                    os.write(f.fileno(), to_write)
                    os.fsync(f.fileno())
            else:
                iterations = (size // CHUNK)
                length = len(str(iterations))
                for i in range(iterations):
                    os.write(f.fileno(), to_write)
                    os.fsync(f.fileno())
                    data['job'].set_progress(float(f'{i / iterations:.{length}f}') * 100)

    @accepts(
        Str('dev'),
        Str('mode', enum=['QUICK', 'FULL', 'FULL_RANDOM'], required=True),
        Bool('synccache', default=True),
        Ref('swap_removal_options'),
    )
    @job(lock=lambda args: args[0])
    async def wipe(self, job, dev, mode, sync, options=None):
        """
        Performs a wipe of a disk `dev`.
        It can be of the following modes:
          - QUICK: clean the first few and last megabytes of every partition and disk
          - FULL: write whole disk with zero's
          - FULL_RANDOM: write whole disk with random bytes
        """
        await self.middleware.call('disk.swaps_remove_disks', [dev], options)
        await self.middleware.call('disk.remove_disk_from_graid', dev)
        await self.middleware.run_in_thread(self._wipe, {'job': job, 'dev': dev, 'mode': mode})
        await self.middleware.call('disk.sync', dev) if sync else None
