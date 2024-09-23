import os

from middlewared.utils.directoryservices import (
    krb5, krb5_constants
)
from middlewared.utils.directoryservices.health import (
    KRB5HealthCheckFailReason, KRB5HealthError
)


class KerberosHealthMixin:
    """
    Base directory services class. This provides common status-related code
    for directory
    """

    def _recover_krb5(self, error: KRB5HealthError) -> None:
        # For now we can simply try to start kerberos
        # to recover from the health issue.
        #
        # This fixes permissions on files (which generates additional
        # error messages regarding type of changes made), gets a
        # fresh kerberos ticket, and sets up a transient job to
        # renew our tickets.
        self.logger.warning(
            'Attempting to recover kerberos service after health '
            'check failure for the following reason: %s',
            error.errmsg
        )
        self.middleware.call_sync('kerberos.start')

    def _health_check_krb5(self) -> None:
        """
        Individual directory services may call this within their
        `_health_check_impl()` method if the directory service uses
        kerberos.
        """
        try:
            st = os.stat('/etc/krb5.conf')
        except FileNotFoundError:
            faulted_reason = (
                'Kerberos configuration file is missing. This may indicate '
                'the file was accidentally deleted by a user with '
                'admin shell access to the TrueNAS server.'
            )

            raise KRB5HealthError(
                KRB5HealthCheckFailReason.KRB5_NO_CONFIG,
                faulted_reason
            )

        if (err_str := self._perm_check(st, 0o644)) is not None:
            faulted_reason = (
                'Unexpected permissions or ownership on the kerberos '
                f'configuration file: {err_str}'
            )
            raise KRB5HealthError(
                KRB5HealthCheckFailReason.KRB5_CONFIG_PERM,
                faulted_reason
            )

        try:
            st = os.stat(krb5_constants.KRB_Keytab.SYSTEM.value)
        except FileNotFoundError:
            faulted_reason = (
                'System keytab is missing. This may indicate that an administrative '
                'action was taken to remove the required machine account '
                'keytab from the TrueNAS server. Rejoining domain may be '
                'required in order to resolve this issue.'
            )
            raise KRB5HealthError(
                KRB5HealthCheckFailReason.KRB5_NO_KEYTAB,
                faulted_reason
            )

        if (err_str := self._perm_check(st, 0o600)) is not None:
            faulted_reason = (
                'Unexpected permissions or ownership on the keberos keytab '
                f'file: {err_str} '
                'This error may have exposed the TrueNAS server\'s host principal '
                'credentials to unauthorized users. Revoking keytab and rejoining '
                'domain may be required.'
            )
            raise KRB5HealthError(
                KRB5HealthCheckFailReason.KRB5_KEYTAB_PERM,
                faulted_reason
            )

        if not krb5.gss_get_current_cred(krb5_constants.krb5ccache.SYSTEM.value, raise_error=False):
            faulted_reason = (
                'Kerberos ticket for domain is expired. Failure to renew '
                'kerberos ticket may indicate issues with DNS resolution or '
                'IPA domain or realm changes that need to be accounted for '
                'in the TrueNAS configuration.'
            )
            raise KRB5HealthError(
                KRB5HealthCheckFailReason.KRB5_TKT_EXPIRED,
                faulted_reason
            )
