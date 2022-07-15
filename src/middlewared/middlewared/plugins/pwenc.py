import base64
import fcntl
import os
import threading

from contextlib import contextmanager
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

from middlewared.plugins.cluster_linux.utils import CTDBConfig, FuseConfig
from middlewared.service import Service
from middlewared.service_exception import CallError
from middlewared.utils.path import pathref_open

PWENC_BLOCK_SIZE = 32
PWENC_FILE_SECRET = os.environ.get('FREENAS_PWENC_SECRET', '/data/pwenc_secret')
PWENC_PADDING = b'{'
PWENC_CHECK = 'Donuts!'

CLPWENC_PATH = os.path.join(
    FuseConfig.FUSE_PATH_BASE.value,
    CTDBConfig.CTDB_VOL_NAME.value,
)


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

    def generate_secret(self, reset_passwords=True):
        secret = os.urandom(PWENC_BLOCK_SIZE)
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
            with open(cls.secret_path, 'rb', opener=cls._secret_opener) as f:
                cls.secret = f.read()

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
    secret_path = os.path.join(
        CLPWENC_PATH,
        '.cluster_private',
        'clpwenc_secret'
    )

    def _reset_passwords(self):
        return

    @staticmethod
    def _secret_opener(path, flags):
        with pathref_open(CLPWENC_PATH, force=True, mode=0o755) as ctdb_path:
            st = os.fstat(ctdb_path)
            if st.st_ino != 1:
                raise CallError(
                    f'Unexpected inode number on {CLPWENC_PATH}. '
                    'This strongly indicates that the ctdb shared volume '
                    'is no longer mounted.'
                )

            with pathref_open(
                ".cluster_private", mode=0o700, dir_fd=ctdb_path, mkdir=True
            ) as priv:
                return os.open(os.path.basename(path), flags, dir_fd=priv)

    @contextmanager
    def check_file(self, flags):
        def opener(path, flags):
            with pathref_open(CLPWENC_PATH, force=True, mode=0o755) as ctdb_path:
                st = os.fstat(ctdb_path)
                if st.st_ino != 1:
                    raise CallError(
                        f'Unexpected inode number on {CLPWENC_PATH}. '
                        'This strongly indicates that the ctdb shared volume '
                        'is no longer mounted.'
                    )

                with pathref_open('.cluster_private', force=True, mode=0o700, dir_fd=ctdb_path) as priv:
                    return os.open(path, flags, dir_fd=priv)

        out_file = open('.check_file', flags, opener=opener)
        try:
            yield out_file
        finally:
            out_file.close()

    def check(self):
        with self.check_file('r') as f:
            data = f.read()

        return self.decrypt(data) == PWENC_CHECK

    def _reset_pwenc_check_field(self):
        with self.check_file('w') as f:
            f.write(self.encrypt(PWENC_CHECK))

    def generate_secret(self, reset_passwords=True):
        if not self.middleware.call_sync('ctdb.general.healthy'):
            raise CallError('Cluster is unhealthy. Refusing to generate secret')

        super().generate_secret()

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
