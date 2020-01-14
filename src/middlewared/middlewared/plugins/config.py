import asyncio
import contextlib
import glob
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile

from datetime import datetime

from middlewared.schema import Bool, Dict, accepts
from middlewared.service import CallError, Service, job, private
from middlewared.plugins.pwenc import PWENC_FILE_SECRET
from middlewared.plugins.pool import GELI_KEYPATH

CONFIG_FILES = {
    'pwenc_secret': PWENC_FILE_SECRET,
    'geli': GELI_KEYPATH,
    'root_authorized_keys': '/root/.ssh/authorized_keys',
}
FREENAS_DATABASE = '/data/freenas-v1.db'
NEED_UPDATE_SENTINEL = '/data/need-update'
RE_CONFIG_BACKUP = re.compile(r'.*(\d{4}-\d{2}-\d{2})-(\d+)\.db$')


class ConfigService(Service):

    @accepts(Dict(
        'configsave',
        Bool('secretseed', default=False),
        Bool('pool_keys', default=False),
        Bool('root_authorized_keys', default=False),
    ))
    @job(pipes=["output"])
    async def save(self, job, options):
        """
        Create a bundle of security-sensitive information. These options select which information
        is included in the bundle:

        `secretseed`: include password secret seed.

        `pool_keys`: include GELI encryption keys.

        `root_authorized_keys`: include "authorized_keys" file for the root user.

        If none of these options are set, the bundle is not generated and the database file is provided.
        """

        if all(not options[k] for k in options):
            bundle = False
            filename = FREENAS_DATABASE
        else:
            bundle = True
            files = CONFIG_FILES.copy()
            if not options['secretseed']:
                files['pwenc_secret'] = None
            if not options['root_authorized_keys'] or not os.path.exists(files['root_authorized_keys']):
                files['root_authorized_keys'] = None
            if not options['pool_keys'] or not os.path.exists(files['geli']) or not os.listdir(files['geli']):
                files['geli'] = None

            filename = tempfile.mkstemp()[1]
            os.chmod(filename, 0o600)
            with tarfile.open(filename, 'w') as tar:
                tar.add(FREENAS_DATABASE, arcname='freenas-v1.db')
                for arcname, path in files.items():
                    if path:
                        tar.add(path, arcname=arcname)

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
            # Currently we compare only the number of migrations for south and django
            # of new and current installed database.
            # This is not bullet proof as we can eventually have more migrations in a stable
            # release compared to a older nightly and still be considered a downgrade, however
            # this is simple enough and works in most cases.
            conn = sqlite3.connect(config_file_name)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM south_migrationhistory WHERE app_name != 'freeadmin'"
                )
                new_numsouth = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM django_migrations WHERE app != 'freeadmin' and app != 'vcp'"
                )
                new_num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
            conn = sqlite3.connect(FREENAS_DATABASE)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM south_migrationhistory WHERE app_name != 'freeadmin'"
                )
                numsouth = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM django_migrations WHERE app != 'freeadmin' and app != 'vcp'"
                )
                num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
                if new_numsouth > numsouth or new_num > num:
                    raise CallError(
                        'Failed to upload config, version newer than the '
                        'current installed.'
                    )
        except Exception as e:
            os.unlink(config_file_name)
            raise CallError(f'The uploaded file is not valid: {e}')

        shutil.move(config_file_name, '/data/uploaded.db')
        if bundle:
            for filename, destination in CONFIG_FILES.items():
                file_path = os.path.join(tmpdir, filename)
                if os.path.exists(file_path):
                    if filename == 'geli':
                        # Let's only copy the geli keys and not overwrite the entire directory
                        os.makedirs(CONFIG_FILES['geli'], exist_ok=True)
                        for key_path in os.listdir(file_path):
                            shutil.move(
                                os.path.join(file_path, key_path), os.path.join(destination, key_path)
                            )
                    elif filename == 'pwenc_secret':
                        shutil.move(file_path, '/data/pwenc_secret_uploaded')
                    else:
                        shutil.move(file_path, destination)

        # Now we must run the migrate operation in the case the db is older
        open(NEED_UPDATE_SENTINEL, 'w+').close()

    @accepts(Dict('options', Bool('reboot', default=True)))
    @job(lock='config_reset', logs=True)
    def reset(self, job, options):
        """
        Reset database to configuration defaults.

        If `reboot` is true this job will reboot the system after its completed with a delay of 10
        seconds.
        """
        factorydb = f'{FREENAS_DATABASE}.factory'
        if os.path.exists(factorydb):
            os.unlink(factorydb)

        cp = subprocess.run(
            ['migrate93', '-f', factorydb],
            capture_output=True,
        )
        if cp.returncode != 0:
            job.logs_fd.write(cp.stderr)
            raise CallError('Factory reset has failed.')

        cp = subprocess.run(
            ['migrate113', '-f', factorydb],
            capture_output=True,
        )
        if cp.returncode != 0:
            job.logs_fd.write(cp.stderr)
            raise CallError('Factory reset has failed.')

        cp = subprocess.run(
            ['migrate'],
            env=dict(os.environ, FREENAS_DATABASE=factorydb),
            capture_output=True,
        )
        if cp.returncode != 0:
            job.logs_fd.write(cp.stderr)
            raise CallError('Factory reset has failed.')

        shutil.move(factorydb, FREENAS_DATABASE)

        if options['reboot']:
            self.middleware.run_coroutine(
                self.middleware.call('system.reboot', {'delay': 10}), wait=False,
            )

    @private
    def backup(self):
        systemdataset = self.middleware.call_sync('systemdataset.config')
        if not systemdataset or not systemdataset['path']:
            return

        # Legacy format
        for f in glob.glob(f'{systemdataset["path"]}/*.db'):
            if not RE_CONFIG_BACKUP.match(f):
                continue
            try:
                os.unlink(f)
            except OSError:
                pass

        today = datetime.now().strftime("%Y%m%d")

        newfile = os.path.join(
            systemdataset["path"],
            f'configs-{systemdataset["uuid"]}',
            self.middleware.call_sync('system.version'),
            f'{today}.db',
        )

        dirname = os.path.dirname(newfile)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        shutil.copy(FREENAS_DATABASE, newfile)
