import asyncio
import contextlib
import os
import shutil
import sqlite3
import tarfile
import tempfile

from middlewared.schema import Bool, Dict, accepts
from middlewared.service import CallError, Service, job

FREENAS_DATABASE = '/data/freenas-v1.db'
NEED_UPDATE_SENTINEL = '/data/need-update'


class ConfigService(Service):

    @accepts(Dict(
        'configsave',
        Bool('secretseed', default=False),
    ))
    @job(pipes=["output"])
    async def save(self, job, options=None):
        """
        Provide configuration file.

        secretseed - will include the password secret seed in the bundle.
        """
        if options is None:
            options = {}

        if not options.get('secretseed'):
            bundle = False
            filename = FREENAS_DATABASE
        else:
            bundle = True
            filename = tempfile.mkstemp()[1]
            os.chmod(filename, 0o600)
            with tarfile.open(filename, 'w') as tar:
                tar.add(FREENAS_DATABASE, arcname='freenas-v1.db')
                tar.add('/data/pwenc_secret', arcname='pwenc_secret')

        with open(filename, 'rb') as f:
            await self.middleware.run_in_thread(shutil.copyfileobj, f, job.pipes.output.w)

        if bundle:
            os.remove(filename)

    @accepts()
    @job(pipes=["input"])
    async def upload(self, job):
        """
        Accepts a configuration file via job pipe.
        """
        filename = tempfile.mktemp(dir='/var/tmp/firmware')

        def read_write():
            nreads = 0
            with open(filename, 'wb') as f_tmp:
                while True:
                    read = job.pipes.input.r.read(1024)
                    if read == b'':
                        break
                    f_tmp.write(read)
                    nreads += 1
                    if nreads > 10240:
                        # FIXME: transfer to a file on disk
                        raise ValueError('File is bigger than 10MiB')
        try:
            await self.middleware.run_in_thread(read_write)
            await self.middleware.run_in_thread(self.__upload, filename)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(filename)
        asyncio.ensure_future(self.middleware.call('system.reboot', {'delay': 10}))

    def __upload(self, config_file_name):
        try:
            """
            First we try to open the file as a tar file.
            We expect the tar file to contain at least the freenas-v1.db.
            It can also contain the pwenc_secret file.
            If we cannot open it as a tar, we try to proceed as it was the
            raw database file.
            """
            try:
                with tarfile.open(config_file_name) as tar:
                    bundle = True
                    tmpdir = tempfile.mkdtemp(dir='/var/tmp/firmware')
                    tar.extractall(path=tmpdir)
                    config_file_name = os.path.join(tmpdir, 'freenas-v1.db')
            except tarfile.ReadError:
                bundle = False
            conn = sqlite3.connect(config_file_name)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM south_migrationhistory WHERE app_name != 'freeadmin'"
                )
                new_num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
            conn = sqlite3.connect(FREENAS_DATABASE)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM south_migrationhistory WHERE app_name != 'freeadmin'")
                num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
                if new_num > num:
                    raise CallError(
                        'Failed to upload config, version newer than the '
                        'current installed.'
                    )
        except Exception:
            os.unlink(config_file_name)
            raise CallError('The uploaded file is not valid.')

        shutil.move(config_file_name, '/data/uploaded.db')
        if bundle:
            secret = os.path.join(tmpdir, 'pwenc_secret')
            if os.path.exists(secret):
                shutil.move(secret, self.middleware.call_sync('pwenc.file_secret_path'))

        # Now we must run the migrate operation in the case the db is older
        open(NEED_UPDATE_SENTINEL, 'w+').close()
