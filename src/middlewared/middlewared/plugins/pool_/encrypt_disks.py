import os
from tempfile import NamedTemporaryFile

from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def encrypt_disks(self, job, disks, options):
        """
        This GELI encrypts all the disks in `disks`.
        NOTE: this is only called on pool.update since GELI was deprecated
        for all newly created zpools.
        """
        # we do not allow the creation of new GELI based zpools, however,
        # we still have to support users who created them before we deprecated
        # the parameters in the API. This is here for those users.
        total_disks = len(disks)
        pass_file = None
        formatted = 0
        if options.get('passphrase'):
            pass_file = await self.middleware.call('pool.create_temp_pass_file', options)

        async def encrypt_disk(disk):
            nonlocal formatted
            dev = disk['devname'].removesuffix('.eli')
            await self.middleware.call('disk.encrypt', dev, options['enc_keypath'], pass_file)
            formatted += 1
            job.set_progress(25, f'Encrypted disk ({formatted}/{total_disks})')

        await asyncio_map(encrypt_disk, disks, limit=16)

        if pass_file:
            await self.middleware.call('pool.remove_temp_pass_file', pass_file)

    @private
    def create_temp_pass_file(self, options):
        with NamedTemporaryFile(mode='w+', dir='/tmp', delete=False) as p:
            os.chmod(p.name, 0o600)
            p.write(options['passphrase'])
            p.flush()
            return p.name

    @private
    def remove_temp_pass_file(self, pass_file):
        try:
            os.remove(pass_file)
        except FileNotFoundError:
            pass
