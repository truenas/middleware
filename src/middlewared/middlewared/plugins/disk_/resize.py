import os
import asyncio
import subprocess

from middlewared.utils import run
from middlewared.service import Service, CallError, private, accepts, returns, job, ValidationErrors
from middlewared.schema import Dict, Str, Int, List, Bool


class UnexpectedFailure(Exception):
    pass


class DiskService(Service):

    @private
    async def resize_impl(self, disk):
        cmd = ['disk_resize', disk['name']]
        err = f'DISK: {disk["name"]!r}'
        if disk['size']:
            err += f' SIZE: {disk["size"]} gigabytes'
            cmd.append(f'{disk["size"]}G')

        try:
            cp = await run(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        except Exception as e:
            err += f' ERROR: {str(e)}'
            raise UnexpectedFailure(err)
        else:
            if cp.returncode != 0:
                err += f' ERROR: {cp.stdout}'
                raise OSError(cp.returncode, os.strerror(cp.returncode), err)

    @accepts(
        List('disks', required=True, items=[
            Dict(
                Str('name', required=True),
                Int('size', required=False, default=None),
            )
        ]),
        Bool('sync', default=True),
        Bool('raise_error', default=False)
    )
    @returns()
    @job(lock='disk_resize')
    async def resize(self, job, data, sync, raise_error):
        """
        Takes a list of disks. Each list entry is a dict that requires a key, value pair.
        `name`: string (the name of the disk (i.e. sda))
        `size`: integer (given in gigabytes)
        `sync`: boolean, when true (default) will synchronize the new size of the disk(s)
            with the database cache.
        `raise_error`: boolean
            when true, will raise a `CallError` if any failures occur
            when false, will will log the errors if any failures occur

        NOTE:
            if `size` is given, the disk with `name` will be resized
                to `size` (overprovision).
            if `size` is not given, the disk with `name` will be resized
                to it's original size (unoverprovision).
        """
        verrors = ValidationErrors()
        disks = []
        for disk in data:
            if disk['name'] in disks:
                verrors.add('disk.resize', 'Disk {disk["name"]!r} specified more than once.')
            else:
                disks.append(disk['name'])

        verrors.check()

        exceptions = await asyncio.gather(*[self.resize_impl(disk) for disk in data], return_exceptions=True)
        failures = []
        success = []
        for disk, exc in zip(data, exceptions):
            if isinstance(exc, Exception):
                failures.append(str(exc))
            else:
                self.logger.info('Successfully resized %r', disk['name'])
                success.append(disk['name'])

        if sync and success:
            if len(success) > 1:
                await (await self.middleware.call('disk.sync_all')).wait()
            else:
                await self.middleware.call('disk.sync', success[0]['name'])

        if failures:
            err = f'Failure resizing: {", ".join(failures)}'
            if raise_error:
                raise CallError(err)
            else:
                self.logger.error(err)
