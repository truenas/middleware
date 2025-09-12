import base64
import fcntl
import os
import threading

from contextlib import contextmanager
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

from middlewared.service import Service
from middlewared.utils.path import pathref_open

PWENC_BLOCK_SIZE = 32
PWENC_FILE_SECRET = os.environ.get('FREENAS_PWENC_SECRET', '/data/pwenc_secret')
PWENC_FILE_SECRET_MODE = 0o600
PWENC_PADDING = b'{'
PWENC_CHECK = 'Donuts!'


class PWEncService(Service):

    secret = None
    secret_path = PWENC_FILE_SECRET
    lock = threading.RLock()

    class Config:
        private = True

    def file_secret_path(self):
        return self.secret_path

    def _reset_passwords(self):
        for table, field, value in (
            ('services_ups', 'ups_monpwd', ''),
            ('system_email', 'em_pass', ''),
            ('system_certificate', 'cert_domains_authenticators', 'NULL'),
            # The following removes all DS-related config and disables directory services
            ('services_cifs', 'cifs_srv_secrets', 'NULL'),
            ('directoryservices', 'enable', '0'),
            ('directoryservices', 'service_type', 'NULL'),
            ('directoryservices', 'cred_type', 'NULL'),
            ('directoryservices', 'cred_ldap_plain', 'NULL'),
            ('directoryservices', 'cred_ldap_mtls_cert_id', 'NULL'),
            ('directoryservices', 'cred_krb5', 'NULL'),
            ('directoryservices', 'ad_trusted_domains', 'NULL'),
        ):
            value = value or "''"
            self.middleware.call_sync('datastore.sql', f'UPDATE {table} SET {field} = {value}')

        self.middleware.call_sync('datastore.sql', 'DELETE FROM directoryservice_kerberoskeytab')
        self.middleware.call_sync('datastore.sql', 'DELETE FROM tasks_cloud_backup')
        self.middleware.call_sync('datastore.sql', 'DELETE FROM tasks_cloudsync')
        self.middleware.call_sync('datastore.sql', 'DELETE FROM system_cloudcredentials')
        self.middleware.call_sync('datastore.sql', 'DELETE FROM system_acmednsauthenticator')
        self.middleware.call_sync(
            'datastore.sql',
            'DELETE FROM storage_replication WHERE repl_ssh_credentials_id IS NOT NULL',
        )
        self.middleware.call_sync('datastore.sql', 'DELETE FROM tasks_rsync WHERE rsync_ssh_credentials_id IS NOT NULL')
        self.middleware.call_sync('datastore.sql', 'DELETE FROM system_keychaincredential')
        # If config is restored without secret seed then SMB auth won't be possible. Disable SMB for all users.
        self.middleware.call_sync('datastore.sql', 'UPDATE account_bsdusers SET bsdusr_smb=0')

    @staticmethod
    def _secret_opener(path, flags):
        with pathref_open(os.path.dirname(path), force=True, expected_mode=0o755) as secret_path:
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

    def _write_secret(self, secret):
        with open(self.secret_path, 'wb', opener=self._secret_opener) as f:
            with self._lock_secrets(f.fileno()):
                os.fchmod(f.fileno(), PWENC_FILE_SECRET_MODE)
                f.write(secret)
                f.flush()
                os.fsync(f.fileno())

                self.reset_secret_cache()
                self._reset_pwenc_check_field()
                self._reset_passwords()

    def generate_secret(self):
        self._write_secret(os.urandom(PWENC_BLOCK_SIZE))

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


async def setup(middleware):
    if not await middleware.call('pwenc.check'):
        middleware.logger.debug('Generating new pwenc secret')
        await middleware.call('pwenc.generate_secret')


def encrypt(data):
    data = data.encode('utf8')

    def pad(x):
        return x + (PWENC_BLOCK_SIZE - len(x) % PWENC_BLOCK_SIZE) * PWENC_PADDING

    nonce = os.urandom(8)
    enc_service = PWEncService

    cipher = AES.new(enc_service.get_secret(), AES.MODE_CTR, counter=Counter.new(64, prefix=nonce))
    encoded = base64.b64encode(nonce + cipher.encrypt(pad(data)))
    return encoded.decode()


def decrypt(encrypted, _raise=False):
    if not encrypted:
        return ''

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
