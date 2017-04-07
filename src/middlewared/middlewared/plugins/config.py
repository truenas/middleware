from middlewared.schema import Bool, Dict, accepts
from middlewared.service import Service, job

import gevent
import os
import tarfile
import tempfile


class ConfigService(Service):

    @accepts(Dict(
        'configsave',
        Bool('secretseed', default=False),
    ))
    @job(pipe=True)
    def save(self, job, options=None):
        """
        Provide configuration file.

        secretseed - will include the password secret seed in the bundle.
        """
        if options is None:
            options = {}

        if not options.get('secretseed'):
            bundle = True
            filename = '/data/freenas-v1.db'
        else:
            bundle = True
            filename = tempfile.mkstemp()[1]
            os.chmod(filename, 0o600)
            with tarfile.open(filename, 'w') as tar:
                tar.add('/data/freenas-v1.db', arcname='freenas-v1.db')
                tar.add('/data/pwenc_secret', arcname='pwenc_secret')

        with open(filename, 'rb') as f:
            f2 = gevent.fileobject.FileObject(job.write_fd, 'wb', close=False)
            while True:
                read = f.read(1024)
                if read == b'':
                    break
                f2.write(read)
            f2.close()
            os.close(job.write_fd)

        if bundle:
            os.remove(filename)
