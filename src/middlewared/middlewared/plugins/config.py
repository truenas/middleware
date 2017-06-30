from middlewared.schema import Bool, Dict, accepts
from middlewared.service import Service, job

import os
import tarfile
import tempfile


class ConfigService(Service):

    @accepts(Dict(
        'configsave',
        Bool('secretseed', default=False),
    ))
    @job(pipe=True)
    async def save(self, job, options=None):
        """
        Provide configuration file.

        secretseed - will include the password secret seed in the bundle.
        """
        if options is None:
            options = {}

        if not options.get('secretseed'):
            bundle = False
            filename = '/data/freenas-v1.db'
        else:
            bundle = True
            filename = tempfile.mkstemp()[1]
            os.chmod(filename, 0o600)
            with tarfile.open(filename, 'w') as tar:
                tar.add('/data/freenas-v1.db', arcname='freenas-v1.db')
                tar.add('/data/pwenc_secret', arcname='pwenc_secret')

        def read_write():
            with open(filename, 'rb') as f:
                f2 = os.fdopen(job.write_fd, 'wb')
                while True:
                    read = f.read(1024)
                    if read == b'':
                        break
                    f2.write(read)
                f2.close()
        await self.middleware.threaded(read_write)

        if bundle:
            os.remove(filename)

    @accepts()
    @job(pipe=True)
    async def upload(self, job):
        """
        Accepts a configuration file via job pipe.
        """
        filename = tempfile.mktemp(dir='/var/tmp/firmware')

        def read_write():
            f = os.fdopen(job.read_fd, 'rb')
            nreads = 0
            with open(filename, 'wb') as f_tmp:
                while True:
                    read = f.read(1024)
                    if read == b'':
                        break
                    f_tmp.write(read)
                    nreads += 1
                    if nreads > 10240:
                        # FIXME: transfer to a file on disk
                        raise ValueError('File is bigger than 10MiB')
        await self.middleware.threaded(read_write)
        rv = await self.middleware.call('notifier.config_upload', filename)
        if not rv[0]:
            raise ValueError(rv[1])
        await self.middleware.call('system.reboot', {'delay': 10})
