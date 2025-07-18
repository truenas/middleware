import subprocess

from base64 import b64decode
from middlewared.utils.directoryservices.ad import get_domain_info
from middlewared.utils.directoryservices.ad_constants import (
    MACHINE_ACCOUNT_KT_NAME,
    MAX_SERVER_TIME_OFFSET,
)
from middlewared.utils.directoryservices.constants import DEF_SVC_OPTS
from middlewared.utils.directoryservices.credential import kinit_with_cred
from middlewared.utils.directoryservices.health import (
    ADHealthCheckFailReason,
    ADHealthError,
)
from middlewared.utils.directoryservices.krb5 import kdc_saf_cache_get, krb5ccache
from middlewared.utils.directoryservices.krb5_conf import KRB5Conf
from middlewared.utils.directoryservices.krb5_constants import (
    KRB_LibDefaults,
    PERSISTENT_KEYRING_PREFIX,
)
from middlewared.utils.directoryservices.krb5_error import KRB5Error, KRB5ErrCode
from middlewared.plugins.idmap_.idmap_winbind import WBClient
from middlewared.service_exception import CallError, MatchNotFound


class ADHealthMixin:

    def _test_machine_account_password(
        self,
        kdc: str,
        account_password: bytes
    ) -> None:
        """
        Validate that our machine account password can be used to kinit
        """
        ds_config = self.middleware.call_sync('directoryservices.config')
        netbiosname = self.middleware.call_sync('smb.config')['netbiosname']

        # Write temporary krb5.conf targeting kdc. Since this is a health check we
        # don't want to introduce a server affinity
        krbconf = KRB5Conf()
        krbconf.add_libdefaults({
            str(KRB_LibDefaults.DEFAULT_REALM): ds_config['kerberos_realm'],
            str(KRB_LibDefaults.DNS_LOOKUP_REALM): 'false',
            str(KRB_LibDefaults.FORWARDABLE): 'true',
            str(KRB_LibDefaults.DEFAULT_CCACHE_NAME): PERSISTENT_KEYRING_PREFIX + '%{uid}'
        })
        krbconf.add_realms([{
            'realm': ds_config['kerberos_realm'] or ds_config['configuration']['domain'],
            'primary_kdc': None,
            'admin_server': [],
            'kdc': [kdc],
            'kpasswd_server': [],
        }])
        krbconf.write()

        cred = {
            'credential_type': 'KERBEROS_USER',
            'username': netbiosname,
            'password': b64decode(account_password).decode(),
        }

        kinit_with_cred(cred, ccache=krb5ccache.TEMP.value)

        # remove our ticket
        self.middleware.call_sync('kerberos.kdestroy', {'ccache': 'TEMP'})

        # regenerate krb5.conf
        self.middleware.call_sync('etc.generate', 'kerberos')

    def _recover_keytab(self) -> None:
        """
        TrueNAS administrator has deleted the active directory machine account
        keytab. We can most likely recover it using the stored secrets in Samba's
        secrets.tdb file.
        """
        self.logger.warning('Attempting to recover from missing machine account keytab')
        # Use net command to build a kerberos keytab from our stored secrets
        results = subprocess.run(['net', 'ads', 'keytab', 'create'], check=False, capture_output=True)
        if results.returncode != 0:
            raise CallError(
                f'Failed to generate kerberos keytab from stored secrets: {results.stderr.decode()}'
            )

        self.middleware.call_sync('kerberos.keytab.store_ad_keytab')
        self.logger.warning('Recovered from missing machine account keytab')

    def _recover_secrets(self) -> None:
        """
        The secrets.tdb file is missing or lacks an entry for our server. We keep a backup
        copy of this in our database. Restore the old one and attempt to kinit with the
        credentials it contains.
        """
        self.logger.warning('Attempting to recover from broken or missing AD secrets file')
        ds_config = self.middleware.call_sync('directoryservices.config')
        smb_config = self.middleware.call_sync('smb.config')
        domain_info = get_domain_info(ds_config['configuration']['domain'])

        if not self.middleware.call_sync('directoryservices.secrets.restore', smb_config['netbiosname']):
            raise CallError(
                'File containing AD machine account password has been removed without a viable '
                'candidate for restoration. Full rejoin of active directory will be required.'
            )

        machine_pass = self.middleware.call_sync(
            'directoryservices.secrets.get_machine_secret',
            smb_config['workgroup']
        )

        # libads may select a different KDC than the one we used for join. This can happen if we fail over shortly
        # after joining AD or a machine account password change.
        kdc_override = kdc_saf_cache_get() or domain_info['kdc_server']

        try:
            self._test_machine_account_password(kdc_override, machine_pass)
        except KRB5Error as krberr:
            match krberr.krb5_code:
                case KRB5ErrCode.KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN:
                    faulted_reason = (
                        f"The domain controller at {kdc_override} said that the "
                        "TrueNAS computer account does not exist. This happened after the "
                        "TrueNAS server tried to recover the secret from a saved backup. "
                        "This means that the TrueNAS account was deleted or that the domain "
                        "controllers do not agree about the list of computer accounts. "
                        "You may need to re-join TrueNAS to Active Directory. "
                    )
                case KRB5ErrCode.KRB5_PREAUTH_FAILED:
                    faulted_reason = (
                        f"The domain controller at {kdc_override} said that the "
                        "TrueNAS computer account credentials are not valid. This means that "
                        "saved credentials on TrueNAS do not match the credentials expected by"
                        "the domain controller. This can happen if the TrueNAS configuration was "
                        "restored from a backup, if the domain controllers in the domain do "
                        "not agree about the credentials, or if someone changed the TrueNAS "
                        "credentials through an unsupported method. You may need to re-join "
                        "TrueNAS to Active Directory."
                    )
                case _:
                    faulted_reason = f'Failed to validate stored credential: {krberr.errmsg}'

            raise ADHealthError(ADHealthCheckFailReason.AD_SECRET_INVALID, faulted_reason)

        self.logger.warning('Recovered from broken or missing AD secrets file')

    def _recover_ad(self, error: ADHealthError) -> None:
        """
        Attempt to recover from an ADHealthError that was raised during
        our health check.
        """
        match error.reason:
            case ADHealthCheckFailReason.AD_KEYTAB_INVALID:
                self._recover_keytab()
            case ADHealthCheckFailReason.AD_SECRET_FILE_MISSING:
                self._recover_secrets()
            case ADHealthCheckFailReason.AD_SECRET_ENTRY_MISSING:
                self._recover_secrets()
            case ADHealthCheckFailReason.AD_NETLOGON_FAILURE:
                # It's possible that our smb.conf has incorrect
                # information in it. We'll try to regenerate the config
                # file and the restart winbindd for good measure
                self.middleware.call_sync('etc.generate', 'smb')
            case ADHealthCheckFailReason.WINBIND_STOPPED:
                # pick up winbind restart below
                pass
            case _:
                # not recoverable
                raise error from None

        self.middleware.call_sync('service.control', 'RESTART', 'idmap', DEF_SVC_OPTS).wait_sync(raise_error=True)

    def _health_check_ad(self):
        """
        Perform basic health checks for AD connection.

        This method is called periodically from our alert framework.
        """

        # We should validate some basic AD configuration before the common
        # kerberos health checks. This will expose issues with clock slew
        # and invalid stored machine account passwords
        config = self.middleware.call_sync('directoryservices.config')
        try:
            domain_info = get_domain_info(config['configuration']['domain'])
        except Exception:
            domain_info = None

        workgroup = self.middleware.call_sync('smb.config')['workgroup']

        if domain_info:
            if domain_info['server_time_offset'] > MAX_SERVER_TIME_OFFSET:
                faulted_reason = (
                    'Time offset from Active Directory domain exceeds maximum '
                    'permitted value. This may indicate an NTP misconfiguration.'
                )
                raise ADHealthError(
                    ADHealthCheckFailReason.NTP_EXCESSIVE_SLEW,
                    faulted_reason
                )

        try:
            machine_pass = self.middleware.call_sync('directoryservices.secrets.get_machine_secret', workgroup)
        except FileNotFoundError:
            # our secrets.tdb file has been deleted for some reason
            # unfortunately sometimes users do this when trying to debug issues
            faulted_reason = (
                'File containing Active Directory machine account password is missing from server.'
            )
            raise ADHealthError(
                ADHealthCheckFailReason.AD_SECRET_FILE_MISSING,
                faulted_reason
            )
        except MatchNotFound:
            faulted_reason = (
                'Active Directory secrets file lacks an entry for this TrueNAS server.'
            )
            raise ADHealthError(
                ADHealthCheckFailReason.AD_SECRET_ENTRY_MISSING,
                faulted_reason
            )

        if domain_info:
            try:
                self._test_machine_account_password(
                    domain_info['kdc_server'],
                    machine_pass
                )
            except (CallError, KRB5Error):
                faulted_reason = (
                    'Stored machine account secret is invalid. This may indicate that '
                    'the machine account password was reset in Active Directory without '
                    'corresponding changes being made to the TrueNAS server configuration.'
                )
                raise ADHealthError(
                    ADHealthCheckFailReason.AD_SECRET_INVALID,
                    faulted_reason
                )

        try:
            self.middleware.call_sync('kerberos.keytab.query', [
                ['name', '=', MACHINE_ACCOUNT_KT_NAME]
            ], {'get': True})
        except MatchNotFound:
            faulted_reason = (
                'Machine account keytab is absent from TrueNAS configuration.'
            )
            raise ADHealthError(
                ADHealthCheckFailReason.AD_KEYTAB_INVALID,
                faulted_reason
            )

        # Now check that winbindd is started

        if not self.middleware.call_sync('service.started', 'idmap'):
            try:
                self.middleware.call_sync('service.control', 'START', 'idmap', DEF_SVC_OPTS).wait_sync(raise_error=True)
            except CallError as e:
                faulted_reason = str(e.errmsg)
                raise ADHealthError(
                    ADHealthCheckFailReason.WINBIND_STOPPED,
                    faulted_reason
                )

        # Winbind is running and so we can check our netlogon connection
        # First open the libwbclient handle. This should in theory never fail.
        try:
            ctx = WBClient()
        except Exception as e:
            faulted_reason = str(e)
            raise ADHealthError(
                ADHealthCheckFailReason.AD_WBCLIENT_FAILURE,
                faulted_reason
            )

        # If needed we can replace `ping_dc()` with `check_trust()`
        # for now we're defaulting to lower-cost test unless it gives
        # false reports of being up
        try:
            ctx.ping_dc()
        except Exception as e:
            faulted_reason = str(e)
            raise ADHealthError(
                ADHealthCheckFailReason.AD_NETLOGON_FAILURE,
                faulted_reason
            )
