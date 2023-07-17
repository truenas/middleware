import base64
import fcntl
import os
import threading

from contextlib import contextmanager
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.plugins.gluster_linux.utils import GlusterConfig
from middlewared.service import Service
from middlewared.utils.path import pathref_open

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
    secret_path = GlusterConfig.SECRETS_FILE.value
    lock = threading.RLock()

    def _write_secret(self, secret, reset_passwords):
        raise NotImplementedError

    def generate_secret(self, reset_passwords=True):
        # secret is derived from our pre-shared localevent secret
        raise NotImplementedError

    def _reset_passwords(self):
        raise NotImplementedError

    def _read_secret(self):
        with open(self.secret_path, 'r', opener=self._secret_opener) as f:
            self.secret = bytes.fromhex(f.read())

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
