import base64
import errno
import fcntl
import json
import pyglfs
import os
import stat
import threading

from contextlib import contextmanager
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.plugins.gluster_linux.pyglfs_utils import glfs, lock_file_open
from middlewared.service import Service
from middlewared.utils.path import pathref_open
from pathlib import Path

PWENC_BLOCK_SIZE = 32
PWENC_FILE_SECRET = os.environ.get('FREENAS_PWENC_SECRET', '/data/pwenc_secret')
PWENC_PADDING = b'{'
PWENC_CHECK = 'Donuts!'

CTDB_VOL_INFO_FILE = CTDBConfig.CTDB_VOL_INFO_FILE.value


class PWEncService(Service):

    secret = None
    secret_path = PWENC_FILE_SECRET
    lock = threading.RLock()

    class Config:
        private = True

    def file_secret_path(self):
        return self.secret_path

    def _reset_passwords(self):
        for table, field in (
            ('directoryservice_activedirectory', 'ad_bindpw'),
            ('directoryservice_ldap', 'ldap_bindpw'),
            ('services_dynamicdns', 'ddns_password'),
            ('services_webdav', 'webdav_password'),
            ('services_ups', 'ups_monpwd'),
            ('system_email', 'em_pass'),
        ):
            self.middleware.call_sync('datastore.sql', f'UPDATE {table} SET {field} = \'\'')

    @staticmethod
    def _secret_opener(path, flags):
        with pathref_open(os.path.dirname(path), force=True, mode=0o755) as secret_path:
            return os.open(os.path.basename(path), flags, dir_fd=secret_path)

    def _reset_pwenc_check_field(self):
        settings = self.middleware.call_sync('datastore.config', 'system.settings')
        self.middleware.call_sync('datastore.update', 'system.settings', settings['id'], {
            'stg_pwenc_check': self.encrypt(PWENC_CHECK),
        })

    @contextmanager
    def _lock_secrets(self, fd):
        with self.lock:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield fd
            finally:
                fcntl.lockf(fd, fcntl.LOCK_UN)

    def _read_secret(self):
        with open(self.secret_path, 'rb', opener=self._secret_opener) as f:
            self.secret = f.read()

    def _write_secret(self, secret, reset_passwords):
        with open(self.secret_path, 'wb', opener=self._secret_opener) as f:
            with self._lock_secrets(f.fileno()):
                os.fchmod(f.fileno(), 0o600)
                f.write(secret)
                f.flush()
                os.fsync(f.fileno())

                self.reset_secret_cache()
                self._reset_pwenc_check_field()

                if reset_passwords:
                    self._reset_passwords()

    def generate_secret(self, reset_passwords=True):
        self._write_secret(os.urandom(PWENC_BLOCK_SIZE), reset_passwords)

    def check(self):
        try:
            settings = self.middleware.call_sync('datastore.config', 'system.settings')
        except IndexError:
            self.middleware.call_sync('datastore.insert', 'system.settings', {})
            settings = self.middleware.call_sync('datastore.config', 'system.settings')

        return self.decrypt(settings['stg_pwenc_check']) == PWENC_CHECK

    @classmethod
    def get_secret(cls):
        if cls.secret is None:
            cls._read_secret(cls)

        return cls.secret

    @classmethod
    def reset_secret_cache(cls):
        cls.secret = None

    def encrypt(self, data):
        return encrypt(data)

    def decrypt(self, encrypted, _raise=False):
        return decrypt(encrypted, _raise)


class CLPWEncService(PWEncService):

    class Config:
        private = True

    secret = None
    ctdb_info = None
    secret_dir_uuid = None

    def _secret_permcheck(self, hdl, mode, is_dir):
        if stat.S_IMODE(hdl.cached_stat.st_mode) != 0o700:
            hdl.open(os.O_DIRECTORY if is_dir else os.O_RDWR).fchmod(0o700)

        if hdl.cached_stat.st_uid != 0 or hdl.cached_stat.st_gid != 0:
            hdl.open(os.O_DIRECTORY if is_dir else os.O_RDWR).fchown(0, 0)

    def _lookup_secret_dir_uuid(self):
        with glfs.get_volume_handle(self.ctdb_info['volume_name']) as vol:
            root_hdl = vol.open_by_uuid(self.ctdb_info['uuid'])
            try:
                secret_dir = root_hdl.lookup('.cluster_private')
            except pyglfs.GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise

                secret_dir = root_hdl.mkdir('.cluster_private', mode=0o700)

            self.secret_dir_uuid = secret_dir.uuid

    def _init_secret_dir(self):
        if self.ctdb_info is None:
            self.ctdb_info = json.loads(Path(CTDB_VOL_INFO_FILE).read_text())

        if self.secret_dir_uuid is None:
            self._lookup_secret_dir_uuid()

    def _read_secret(self):
        # Since this is called inside a class method skip _init_secret_dir() call
        ctdb_info = json.loads(Path(CTDB_VOL_INFO_FILE).read_text())
        with glfs.get_volume_handle(ctdb_info['volume_name']) as vol:
            secret_dir = vol.open_by_uuid(ctdb_info['uuid']).lookup('.cluster_private')
            secret = secret_dir.lookup('clpwenc_secret')
            self.secret = secret.contents()

    def _write_secret(self, secret, reset_passwords):
        self._init_secret_dir()
        with glfs.get_volume_handle(self.ctdb_info['volume_name']) as vol:
            secret_dir = vol.open_by_uuid(self.secret_dir_uuid)
            self._secret_permcheck(secret_dir, 0o700, True)
            try:
                secret_file = secret_dir.lookup('clpwenc_secret')
            except pyglfs.GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise
                secret_file = secret_dir.create('clpwenc_secret', os.O_RDWR | os.O_CREAT)

            self._secret_permcheck(secret_file, 0o600, False)
            with lock_file_open(secret_file, os.O_RDWR) as fd:
                fd.ftruncate(0)
                fd.pwrite(secret, 0)
                fd.fsync()

    def _reset_passwords(self):
        raise NotImplementedError

    @staticmethod
    def _secret_opener(path, flags):
        raise NotImplementedError

    def check(self):
        self._init_secret_dir()
        with glfs.get_volume_handle(self.ctdb_info['volume_name']) as vol:
            secret_dir = vol.open_by_uuid(self.secret_dir_uuid)
            self._secret_permcheck(secret_dir, 0o700, True)
            try:
                check_file = secret_dir.lookup('.check_file')

            except pyglfs.GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise

                return False

            return self.decrypt(check_file.contents()) == PWENC_CHECK

    def _reset_pwenc_check_field(self):
        self._init_secret_dir()
        with glfs.get_volume_handle(self.ctdb_info['volume_name']) as vol:
            secret_dir = vol.open_by_uuid(self.secret_dir_uuid)
            self._secret_permcheck(secret_dir, 0o700, True)
            try:
                check_file = secret_dir.lookup('.check_file')

            except pyglfs.GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise
                check_file = secret_dir.create('.check_file', os.O_RDWR)

            with lock_file_open(check_file, os.O_RDWR) as fd:
                fd.ftruncate(0)
                fd.pwrite(self.encrypt(PWENC_CHECK), 0)

    def encrypt(self, data):
        return encrypt(data, True)

    def decrypt(self, encrypted, _raise=False):
        return decrypt(encrypted, _raise, True)


async def setup(middleware):
    if not await middleware.call('pwenc.check'):
        middleware.logger.debug('Generating new pwenc secret')
        await middleware.call('pwenc.generate_secret')


def encrypt(data, cluster=False):
    data = data.encode('utf8')

    def pad(x):
        return x + (PWENC_BLOCK_SIZE - len(x) % PWENC_BLOCK_SIZE) * PWENC_PADDING

    nonce = os.urandom(8)
    if cluster:
        enc_service = CLPWEncService
    else:
        enc_service = PWEncService

    cipher = AES.new(enc_service.get_secret(), AES.MODE_CTR, counter=Counter.new(64, prefix=nonce))
    encoded = base64.b64encode(nonce + cipher.encrypt(pad(data)))
    return encoded.decode()


def decrypt(encrypted, _raise=False, cluster=False):
    if not encrypted:
        return ''

    if cluster:
        enc_service = CLPWEncService
    else:
        enc_service = PWEncService

    try:
        encrypted = base64.b64decode(encrypted)
        nonce = encrypted[:8]
        encrypted = encrypted[8:]

        cipher = AES.new(enc_service.get_secret(), AES.MODE_CTR, counter=Counter.new(64, prefix=nonce))
        return cipher.decrypt(encrypted).rstrip(PWENC_PADDING).decode('utf8')
    except Exception:
        if _raise:
            raise
        return ''
