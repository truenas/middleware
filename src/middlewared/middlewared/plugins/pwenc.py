import os
import truenas_pypwenc

from base64 import b64decode
from tempfile import NamedTemporaryFile
from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.utils.pwenc import encrypt, decrypt, pwenc_generate_secret, pwenc_rename, PWENC_FILE_SECRET
from middlewared.service import pass_app, Service
from middlewared.service_exception import CallError

PWENC_CHECK = 'Donuts!'


class PWEncService(Service):

    class Config:
        private = True

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

    def _reset_pwenc_check_field(self):
        settings = self.middleware.call_sync('datastore.config', 'system.settings')
        self.middleware.call_sync('datastore.update', 'system.settings', settings['id'], {
            'stg_pwenc_check': encrypt(PWENC_CHECK),
        })

    def check(self):
        try:
            settings = self.middleware.call_sync('datastore.config', 'system.settings')
        except IndexError:
            self.middleware.call_sync('datastore.insert', 'system.settings', {})
            settings = self.middleware.call_sync('datastore.config', 'system.settings')

        try:
            return decrypt(settings['stg_pwenc_check']) == PWENC_CHECK
        except truenas_pypwenc.PwencError as exc:
            # In principle on a totally fresh install it's expected that we need to generate a new
            # secret. In this case we expect SECRET_NOT_FOUND. Other errors are unexpected and
            # should be logged
            if exc.code != truenas_pypwenc.PWENC_ERROR_SECRET_NOT_FOUND:
                self.logger.exception('Failed to decrypt stg_pwenc_check')

            return False
        except Exception:
            self.logger.exception('Unexpected error while trying to check pwenc secret')
            return False

    def generate_secret(self):
        pwenc_generate_secret()
        self._reset_pwenc_check_field()
        self._reset_passwords()

    @pass_app()
    def replace(self, app, b64secret):
        """ This method exists purely for use via failover.call_remote from active  controller on HA truenas
        appliance. """
        if app and not isinstance(app.authenticated_credentials, TruenasNodeSessionManagerCredentials):
            raise CallError(f'{type(app.authenticated_credentials)}: unexpected credential type for endpoint.')

        if self.middleware.call_sync('failover.is_single_master_node'):
            raise CallError('pwenc.replace called on controller that is not standby')

        data = b64decode(b64secret)
        if len(data) != truenas_pypwenc.PWENC_BLOCK_SIZE:
            raise CallError('Unexpected data length for pwenc file')

        with open(PWENC_FILE_SECRET, 'rb') as f:
            # avoid triggering inotify / churning our pwenc file if possible. This is so that
            # we don't create unnecessary backup files on a normal sync_to_peer request.
            if f.read() == data:
                return

        self.middleware.logger.info('Received pwenc secret file. Replacing.')
        with NamedTemporaryFile(
            mode='wb',
            dir='/data',
            prefix='.pwenc_secret.',
            suffix='.tmp',
            delete=False
        ) as f:
            temp_path = f.name
            f.write(data)
            f.flush()

        try:
            pwenc_rename(temp_path)
        except Exception:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

            raise


async def setup(middleware):
    if not await middleware.call('pwenc.check'):
        middleware.logger.debug('Generating new pwenc secret')
        await middleware.call('pwenc.generate_secret')
