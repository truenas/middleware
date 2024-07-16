from middlewared.utils.directoryservices.health import (
    LDAPHealthCheckFailReason,
    LDAPHealthError
)
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
            case LDAPHealthCheckFailReason.LDAP_BIND_FAILED:
                self._recover_ldap_config()
            case LDAPHealthCheckFailReason.SSSD_STOPPED:
                # pick up with sssd restart below
                pass
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

        ldap_config = self.middleware.call_sync('ldap.config')

        # There is a small chance we have an oddball generic LDAP + KRB5
        # domain and will need to perform LDAP health checks.
        if ldap_config['kerberos_realm']:
            self._health_check_krb5()


        # Verify that our stored credentials are sufficient to authenticate
        # to LDAP server via python-ldap
        try:
            self.middleware.call_sync('ldap.get_root_DSE')
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
                self.middleware.call_sync('service.start', 'sssd', {'silent': False})
            except CallError as e:
                self._faulted_reason = str(e)
                raise LDAPHealthError(
                    LDAPHealthCheckFailReason.SSSD_STOPPED,
                    self._faulted_reason
                )
