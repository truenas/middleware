import ldap

from middlewared.utils.directoryservices.health import (
    LDAPHealthCheckFailReason,
    LDAPHealthError
)
from middlewared.utils.directoryservices.ldap_client import LdapClient
from middlewared.utils.directoryservices.ldap_utils import ds_config_to_ldap_client_config


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

        self.middleware.call_sync('service.stop', 'sssd')
        self.middleware.call_sync('service.start', 'sssd', {'silent': False})

    def _health_check_ldap(self) -> None:
        """
        Perform basic health checks for IPA connection.

        This method is called periodically from our alert framework.
        """
        data = self.middleware.call_sync('directoryservices.config')
        ldap_config = data['configuration']

        # There is a small chance we have an oddball generic LDAP + KRB5
        # domain and will need to perform LDAP health checks.
        if ldap_config['configuration']['kerberos_realm']:
            self._health_check_krb5()

        # Verify that our stored credentials are sufficient to authenticate
        # to LDAP server via python-ldap and query root dse.
        try:
            client_config = ds_config_to_ldap_client_config(data)
            LdapClient.search(client_config, '', ldap.SCOPE_BASE, '(objectclass=*)')
        except Exception as e:
            self._faulted_reason = str(e)
            raise LDAPHealthError(
                LDAPHealthCheckFailReason.LDAP_BIND_FAILED,
                self._faulted_reason
            )
