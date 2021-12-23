import os

from middlewared.schema import accepts, Bool, Ref, Str, returns
from middlewared.service import job, private, Service


CHUNK = 1048576  # 1MB binary


class DiskService(Service):

    @private
    def _wipe(self, data):
        with open(f'/dev/{data["dev"]}', 'wb') as f:
            size = os.lseek(f.fileno(), os.SEEK_SET, os.SEEK_END)
            if size == 0:
                # no size means nothing else will work
                self.logger.error('Unable to determine size of "%s"', data['dev'])
                return
            elif size < 33554432 and data['mode'] == 'QUICK':
                # we wipe the first and last 33554432 bytes (32MB) of the
                # device when it's the "QUICK" mode so if the device is smaller
                # than that, ignore it.
                return

            # seek back to the beginning of the disk
            os.lseek(f.fileno(), os.SEEK_SET, os.SEEK_SET)

            # no reason to write more than 1MB at a time
            # or kernel will break them into smaller chunks
            if data['mode'] in ('QUICK', 'FULL'):
                to_write = bytearray(CHUNK).zfill(0)
            else:
                to_write = bytearray(os.urandom(CHUNK))

            if data['mode'] == 'QUICK':
                _32 = 32
                for i in range(_32):
                    # wipe first 32MB
                    os.write(f.fileno(), to_write)

                # seek to 32MB before end of drive
                os.lseek(f.fileno(), (size - (CHUNK * _32)), os.SEEK_SET)
                for i in range(_32):
                    # wipe last 32MB
                    os.write(f.fileno(), to_write)
            else:
                iterations = (size // CHUNK)
                length = len(str(iterations))
                for i in range(iterations):
                    os.write(f.fileno(), to_write)
                    data['job'].set_progress(float(f'{i / iterations:.{length}f}') * 100)

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
        await self.middleware.run_in_thread(self._wipe, {'job': job, 'dev': dev, 'mode': mode})
        await self.middleware.call('disk.sync', dev) if sync else None
