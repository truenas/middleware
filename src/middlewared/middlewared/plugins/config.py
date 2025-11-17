import contextlib
from datetime import datetime
import glob
import os
import pathlib
import re
import shutil
import subprocess
import tarfile
import tempfile

from middlewared.api import api_method
from middlewared.api.current import (
    ConfigSaveArgs, ConfigSaveResult, ConfigUploadArgs, ConfigUploadResult, ConfigResetArgs, ConfigResetResult
)
from middlewared.service import CallError, Service, job, private
from middlewared.utils.db import FREENAS_DATABASE
from middlewared.utils.privilege import credential_has_full_admin
from middlewared.utils.pwenc import PWENC_FILE_SECRET

CONFIG_FILES = {
    'pwenc_secret': PWENC_FILE_SECRET,
    'admin_authorized_keys': '/home/admin/.ssh/authorized_keys',
    'truenas_admin_authorized_keys': '/home/truenas_admin/.ssh/authorized_keys',
    'root_authorized_keys': '/root/.ssh/authorized_keys',
}
RE_CONFIG_BACKUP = re.compile(r'.*(\d{4}-\d{2}-\d{2})-(\d+)\.db$')
UPLOADED_DB_PATH = '/data/uploaded.db'
PWENC_UPLOADED = '/data/pwenc_secret_uploaded'
ADMIN_KEYS_UPLOADED = '/data/admin_authorized_keys_uploaded'
TRUENAS_ADMIN_KEYS_UPLOADED = '/data/truenas_admin_authorized_keys_uploaded'
ROOT_KEYS_UPLOADED = '/data/root_authorized_keys_uploaded'
DATABASE_NAME = os.path.basename(FREENAS_DATABASE)
PWENC_SECRET_NAME = os.path.basename(PWENC_FILE_SECRET)
CONFIGURATION_UPLOAD_REBOOT_REASON = 'Configuration upload'
CONFIGURATION_RESET_REBOOT_REASON = 'Configuration reset'


class ConfigService(Service):

    class Config:
        cli_namespace = 'system.config'

    @private
    def save_db_only(self, options, job):
        with open(FREENAS_DATABASE, 'rb') as f:
            shutil.copyfileobj(f, job.pipes.output.w)

    @private
    def save_tar_file(self, options, job):
        with tempfile.NamedTemporaryFile(delete=True) as ntf:
            with tarfile.open(ntf.name, 'w') as tar:
                files = {'freenas-v1.db': FREENAS_DATABASE}
                if options['secretseed']:
                    files['pwenc_secret'] = CONFIG_FILES['pwenc_secret']
                if options['root_authorized_keys'] and os.path.exists(CONFIG_FILES['admin_authorized_keys']):
                    files['admin_authorized_keys'] = CONFIG_FILES['admin_authorized_keys']
                if options['root_authorized_keys'] and os.path.exists(CONFIG_FILES['truenas_admin_authorized_keys']):
                    files['truenas_admin_authorized_keys'] = CONFIG_FILES['truenas_admin_authorized_keys']
                if options['root_authorized_keys'] and os.path.exists(CONFIG_FILES['root_authorized_keys']):
                    files['root_authorized_keys'] = CONFIG_FILES['root_authorized_keys']
                for arcname, path in files.items():
                    tar.add(path, arcname=arcname)

            with open(ntf.name, 'rb') as f:
                shutil.copyfileobj(f, job.pipes.output.w)

    @api_method(ConfigSaveArgs, ConfigSaveResult, roles=['FULL_ADMIN'])
    @job(pipes=["output"])
    async def save(self, job, options):
        """
        Create a tar file of security-sensitive information. These options select which information
        is included in the tar file:

        `secretseed` bool: When true, include password secret seed.
        `pool_keys` bool: IGNORED and DEPRECATED as it does not apply on SCALE systems.
        `root_authorized_keys` bool: When true, include "/root/.ssh/authorized_keys" file for the root user.

        If none of these options are set, the tar file is not generated and the database file is returned.
        """
        self._check_access(job, 'save')

        options.pop('pool_keys')  # ignored, doesn't apply on SCALE

        method = self.save_db_only if not any(options.values()) else self.save_tar_file
        await self.middleware.run_in_thread(method, options, job)

    @api_method(ConfigUploadArgs, ConfigUploadResult, roles=['FULL_ADMIN'], pass_app=True)
    @job(pipes=["input"])
    def upload(self, app, job):
        """
        Accepts a configuration file via job pipe.
        """
        self._check_access(job, "upload")

        job.set_progress(0, 'Reading database file')
        chunk = 1024
        max_size = 10485760  # 10MB
        with tempfile.NamedTemporaryFile() as stf:
            with open(stf.name, 'wb') as f:
                while True:
                    data_in = job.pipes.input.r.read(chunk)
                    if data_in == b'':
                        break
                    else:
                        f.write(data_in)

                    if f.tell() > max_size:
                        raise CallError(f'Uploaded config is greater than maximum allowed size ({max_size} Bytes)')

            is_tar = tarfile.is_tarfile(stf.name)
            self.upload_impl(job, stf.name, is_tar_file=is_tar)

        self.middleware.run_coroutine(
            self.middleware.call('system.reboot', CONFIGURATION_UPLOAD_REBOOT_REASON, {'delay': 10}, app=app),
            wait=False,
        )

    @private
    def upload_impl(self, job, file_or_tar, is_tar_file=False):
        job.set_progress(15, 'Replacing database file')
        with tempfile.TemporaryDirectory() as temp_dir:
            if is_tar_file:
                with tarfile.open(file_or_tar, 'r') as tar:
                    tar.extractall(temp_dir, filter='tar')
            else:
                # if it's just the db then copy it to the same
                # temp directory to keep the logic simple(ish).
                # it's also important that we add a '.db' suffix
                # since we're assuming (since this is a single file)
                # that this is the database only and our logic below
                # assumes the name of the file is freenas-v1.db OR a
                # file that has a '.db' suffix
                shutil.copy2(file_or_tar, f'{temp_dir}/{DATABASE_NAME}')

            pathobj = pathlib.Path(temp_dir)
            found_db_file = None
            for i in pathobj.iterdir():
                if i.name == DATABASE_NAME or i.suffix == '.db':
                    # when user saves their config, we put the db in the
                    # archive using the same name as the db on the local
                    # filesystem, however, in the past we did not do this
                    # so the db was named in an unstructured mannner. We
                    # already make the assumption that the user doesn't
                    # change the name of the pwenc_secret file so we'll
                    # make the assumption that the user can change the
                    # name of the db but doesn't change the suffix.
                    found_db_file = i
                    break

            if found_db_file is None:
                raise CallError('Neither a valid tar or TrueNAS database file was provided.')

            p = subprocess.run([
                'migrate',
                str(found_db_file.absolute()),
                f'{temp_dir}/{PWENC_SECRET_NAME}',
            ], capture_output=True, text=True)
            if p.returncode != 0:
                raise CallError(
                    f'Uploaded TrueNAS database file is not valid:\n{p.stderr}'
                )

            # now copy uploaded files/dirs to respective location
            send_to_remote = []
            for i in pathobj.iterdir():
                abspath = str(i.absolute())
                if i.name == found_db_file.name:
                    shutil.move(abspath, UPLOADED_DB_PATH)
                    send_to_remote.append(UPLOADED_DB_PATH)

                if i.name == 'pwenc_secret':
                    shutil.move(abspath, PWENC_UPLOADED)
                    send_to_remote.append(PWENC_UPLOADED)

                if i.name == 'admin_authorized_keys':
                    shutil.move(abspath, ADMIN_KEYS_UPLOADED)
                    send_to_remote.append(ADMIN_KEYS_UPLOADED)

                if i.name == 'truenas_admin_authorized_keys':
                    shutil.move(abspath, TRUENAS_ADMIN_KEYS_UPLOADED)
                    send_to_remote.append(TRUENAS_ADMIN_KEYS_UPLOADED)

                if i.name == 'root_authorized_keys':
                    shutil.move(abspath, ROOT_KEYS_UPLOADED)
                    send_to_remote.append(ROOT_KEYS_UPLOADED)

        job.set_progress(25, 'Running database upload hooks')
        self.middleware.call_hook_sync('config.on_upload', UPLOADED_DB_PATH)

        self._handle_failover(job, 'uploaded', send_to_remote, UPLOADED_DB_PATH, True,
                              CONFIGURATION_UPLOAD_REBOOT_REASON)

    @api_method(ConfigResetArgs, ConfigResetResult, roles=['FULL_ADMIN'], pass_app=True)
    @job(lock='config_reset', logs=True)
    def reset(self, app, job, options):
        """
        Reset database to configuration defaults.

        If `reboot` is true this job will reboot the system after its completed with a delay of 10
        seconds.
        """
        self._check_access(job, 'reset')

        job.set_progress(15, 'Replacing database file')
        shutil.copy('/data/factory-v1.db', FREENAS_DATABASE)

        job.set_progress(25, 'Running database upload hooks')
        self.middleware.call_hook_sync('config.on_upload', FREENAS_DATABASE)

        self._handle_failover(job, 'reset', [FREENAS_DATABASE], FREENAS_DATABASE, options['reboot'],
                              CONFIGURATION_RESET_REBOOT_REASON)

        if options['reboot']:
            job.set_progress(95, 'Will reboot in 10 seconds')
            self.middleware.run_coroutine(
                self.middleware.call('system.reboot', CONFIGURATION_RESET_REBOOT_REASON, {'delay': 10}, app=app),
                wait=False,
            )

    def _check_access(self, job, verb):
        if job.credentials is None:
            raise CallError('Unable to check credentials')

        if job.credentials.is_user_session and not credential_has_full_admin(job.credentials):
            raise CallError(f'Configuration {verb} is limited to full administrators')

    def _handle_failover(self, job, verb, files, db_path, reboot, reboot_reason):
        if not self.middleware.call_sync('failover.licensed'):
            return

        try:
            job.set_progress(50, 'Sending configuration files to the other node')
            for _file in files:
                self.middleware.call_sync('failover.send_small_file', _file)

            job.set_progress(75, 'Running database upload hooks on the other node')
            self.middleware.call_sync(
                'failover.call_remote', 'core.call_hook', ['config.on_upload', [db_path]],
                {'timeout': 300},  # Give more time for potential initrd update
            )

            if reboot:
                self.middleware.run_coroutine(
                    self.middleware.call('failover.call_remote', 'system.reboot', [reboot_reason]),
                    wait=False,
                )
        except Exception as e:
            raise CallError(
                f'Config {verb} successfully, but remote node responded with error: {e}. '
                f'Please use Sync to Peer on the System/Failover page to perform a manual sync after reboot.',
                CallError.EREMOTENODEERROR,
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


def setup(middleware):
    if os.path.exists(UPLOADED_DB_PATH):
        shutil.move(UPLOADED_DB_PATH, FREENAS_DATABASE)

        if os.path.exists(PWENC_UPLOADED):
            shutil.move(PWENC_UPLOADED, PWENC_FILE_SECRET)
        else:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(PWENC_FILE_SECRET)

        if os.path.exists(ADMIN_KEYS_UPLOADED):
            shutil.move(ADMIN_KEYS_UPLOADED, CONFIG_FILES['admin_authorized_keys'])
        else:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(CONFIG_FILES['admin_authorized_keys'])

        if os.path.exists(TRUENAS_ADMIN_KEYS_UPLOADED):
            shutil.move(TRUENAS_ADMIN_KEYS_UPLOADED, CONFIG_FILES['truenas_admin_authorized_keys'])
        else:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(CONFIG_FILES['truenas_admin_authorized_keys'])

        if os.path.exists(ROOT_KEYS_UPLOADED):
            shutil.move(ROOT_KEYS_UPLOADED, CONFIG_FILES['root_authorized_keys'])
        else:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(CONFIG_FILES['root_authorized_keys'])
