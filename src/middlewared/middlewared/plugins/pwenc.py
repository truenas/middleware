from middlewared.utils.pwenc import encrypt, decrypt, pwenc_generate_secret
from middlewared.service import Service

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

        return decrypt(settings['stg_pwenc_check']) == PWENC_CHECK

    def generate_secret(self):
        pwenc_generate_secret()
        self._reset_pwenc_check_field()
        self._reset_passwords()


async def setup(middleware):
    if not await middleware.call('pwenc.check'):
        middleware.logger.debug('Generating new pwenc secret')
        await middleware.call('pwenc.generate_secret')
