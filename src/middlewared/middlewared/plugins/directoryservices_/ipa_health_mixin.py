import ldap
import os

from middlewared.utils.directoryservices import (
    ipa_constants, ldap_utils
)
from middlewared.utils.directoryservices.health import (
    IPAHealthCheckFailReason,
    IPAHealthError
)
from middlewared.plugins.ldap_.ldap_client import LdapClient
from middlewared.service_exception import CallError


class IPAHealthMixin:
    def _health_check_ipa(self) -> None:
        """
        Perform basic health checks for IPA connection.

        This method is called periodically from our alert framework.
        """

        # First check that kerberos is working correctly
        self._health_check_krb5()

        # Next check that required IPA configuration files exist and have
        # correct permissions
        try:
            st = os.stat(ipa_constants.IPAPath.DEFAULTCONF.path)
        except FileNotFoundError:
            self._faulted_reason = (
                'IPA default_config file is missing. This may indicate that '
                'an administrator has enabled the IPA service through '
                'unsupported methods. Rejoining the IPA domain may be required.'
            )
            raise IPAHealthError(
                IPAHealthCheckFailReason.IPA_NO_CONFIG,
                self._faulted_reason
            )

        if (err_str := self._perm_check(st, ipa_constants.IPAPath.DEFAULTCONF.perm)) is not None:
            self._faulted_reason = (
                'Unexpected permissions or ownership on the IPA default '
                f'configuration file {err_str}'
            )

            raise IPAHealthError(
                IPAHealthCheckFailReason.IPA_CONFIG_PERM,
                self._faulted_reason
            )

        try:
            st = os.stat(ipa_constants.IPAPath.CACERT.path)
        except FileNotFoundError:
            self._faulted_reason = (
                'IPA CA certificate file is missing. This may indicate that '
                'an administrator has enabled the IPA service through '
                'unsupported methods. Rejoining the IPA domain may be required.'
            )
            raise IPAHealthError(
                IPAHealthCheckFailReason.IPA_NO_CACERT,
                self._faulted_reason
            )

        if (err_str := self._perm_check(st, ipa_constants.IPAPath.CACERT.perm)) is not None:
            self._faulted_reason = (
                'Unexpected permissions or ownership on the IPA CA certificate '
                f'file {err_str}'
            )
            raise IPAHealthError(
                IPAHealthCheckFailReason.IPA_CACERT_PERM,
                self._faulted_reason
            )

        config = self.config

        # By this point we know kerberos should be healthy and we should
        # have ticket. Verify we can use our kerberos ticket to access the
        # IPA LDAP server.
        #
        # We're peforming GSSAPI bind with SEAL set so don't bother with
        # ldaps. This is simple query for root DSE to detect whether LDAP
        # connection is profoundly broken.
        uris = ldap_utils.hostnames_to_uris(config['hostname'].split(), False)
        try:
            LdapClient.search({
                'uri_list': uris,
                'bind_type': 'GSSAPI',
                'options': {
                    'timeout': config['timeout'],
                    'dns_timeout': config['dns_timeout'],
                },
                'security': {
                    'ssl': 'OFF',
                    'sasl': 'SEAL'
                }
            }, '', ldap.SCOPE_BASE, '(objectclass=*)')
        except Exception as e:
            self._faulted_reason = str(e)
            raise IPAHealthError(
                IPAHealthCheckFailReason.LDAP_BIND_FAILED,
                self._faulted_reason
            )

        # Finally check that sssd is running, and if it's not, try non-silent
        # start so that we can dump the reason it's failing to start into an alert.
        #
        # We don't want to move the sssd restart into the alert itself because
        # we need to populate the error reason into `_faulted_reason` so that
        # it appears in our directory services summary
        if not self.call_sync('service.started', 'sssd'):
            try:
                self.call_sync('service.start', 'sssd', {'silent': False})
            except CallError as e:
                self._faulted_reason = str(e)
                raise IPAHealthError(
                    IPAHealthCheckFailReason.SSSD_STOPPED,
                    self._faulted_reason
                )
