import ldap

from middlewared.utils.directoryservices.constants import DEF_SVC_OPTS, DSType
from middlewared.utils.directoryservices.credential import dsconfig_to_ldap_client_config
from middlewared.utils.directoryservices.health import (
    LDAPHealthCheckFailReason,
    LDAPHealthError
)
from middlewared.utils.directoryservices.ldap_client import LdapClient
from middlewared.service_exception import CallError


class LDAPHealthMixin:
    def _recover_ldap_config(self) -> list[dict]:
        return self.middleware.call_sync('etc.generate', 'ldap')

    def _recover_ldap(self, error: LDAPHealthError) -> None:
        """
        Attempt to recover from an ADHealthError that was raised during
        our health check.
        """
        match error.reason:
            case LDAPHealthCheckFailReason.LDAP_BIND_FAILED | LDAPHealthCheckFailReason.SSSD_STOPPED:
                self._recover_ldap_config()
            case _:
                # not recoverable
                raise error from None

        self.middleware.call_sync('service.control', 'RESTART', 'sssd', DEF_SVC_OPTS).wait_sync(raise_error=True)

    def _ldap_get_dn(self, dn=None, scope_base=True):
        """
        Outputs contents of specified DN in JSON. By default will target the basedn.
        This is available for development and debug purposes.
        """
        data = self.middleware.call_sync('directoryservices.config')
        if data['service_type'] not in (DSType.LDAP.value, DSType.IPA.value):
            raise CallError('Method not available for directory services type')

        ldap_config = dsconfig_to_ldap_client_config(data)
        return LdapClient.search(
            ldap_config,
            dn or data['configuration']['basedn'],
            ldap.SCOPE_BASE if scope_base else ldap.SCOPE_SUBTREE,
            '(objectclass=*)'
        )

    def _ldap_get_root_dse(self, data: dict) -> dict:
        """
        Use directory service config to retrieve root DSE of an LDAP server
        """
        ldap_config = dsconfig_to_ldap_client_config(data)
        return LdapClient.search(ldap_config, '', ldap.SCOPE_BASE, '(objectclass=*)')

    def _health_check_ldap(self) -> None:
        """
        Perform basic health checks for IPA connection.

        This method is called periodically from our alert framework.
        """

        ds_config = self.middleware.call_sync('directoryservices.config')

        # There is a small chance we have an oddball generic LDAP + KRB5
        # domain and will need to perform LDAP health checks.
        if ds_config['kerberos_realm']:
            self._health_check_krb5()

        # Verify that our stored credentials are sufficient to authenticate
        # to LDAP server via python-ldap
        try:
            self._ldap_get_root_dse(ds_config)
        except Exception as e:
            self._faulted_reason = str(e)
            raise LDAPHealthError(
                LDAPHealthCheckFailReason.LDAP_BIND_FAILED,
                self._faulted_reason
            )

        # Finally check that sssd is running, and if it's not, try non-silent
        # start so that we can dump the reason it's failing to start into an alert.
        #
        # We don't want to move the sssd restart into the alert itself because
        # we need to populate the error reason into `_faulted_reason` so that
        # it appears in our directory services summary
        if not self.middleware.call_sync('service.started', 'sssd'):
            try:
                self.middleware.call_sync('service.control', 'START', 'sssd', {'silent': False}).wait_sync(raise_error=True)
            except CallError as e:
                self._faulted_reason = str(e)
                raise LDAPHealthError(
                    LDAPHealthCheckFailReason.SSSD_STOPPED,
                    self._faulted_reason
                )
