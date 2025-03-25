import os
import stat
import time

from .activedirectory_health_mixin import ADHealthMixin
from .ipa_health_mixin import IPAHealthMixin
from .kerberos_health_mixin import KerberosHealthMixin
from .ldap_health_mixin import LDAPHealthMixin
from middlewared.plugins.ldap_.constants import SERVER_TYPE_FREEIPA
from middlewared.service import Service
from middlewared.service_exception import CallError
from middlewared.utils.directoryservices.constants import DSStatus, DSType
from middlewared.utils.directoryservices.health import (
    ADHealthError, DSHealthObj, IPAHealthError, KRB5HealthError,
    LDAPHealthError, MAX_RECOVER_ATTEMPTS,
)


class DomainHealth(
    Service,
    ADHealthMixin,
    IPAHealthMixin,
    KerberosHealthMixin,
    LDAPHealthMixin,
):

    class Config:
        namespace = 'directoryservices.health'
        cli_private = True
        private = True

    def _get_enabled_ds(self):
        ad = self.middleware.call_sync('datastore.config', 'directoryservice.activedirectory')
        if ad['ad_enable']:
            return DSType.AD

        ldap = self.middleware.call_sync('datastore.config', 'directoryservice.ldap')
        if ldap['ldap_enable'] is False:
            return None

        # For now we are handling the IPA join as a layer on top of LDAP
        # plugin.
        if ldap['ldap_server_type'] == SERVER_TYPE_FREEIPA:
            # there is no way to become healthy for IPA join without a host
            # keytab and so we'll try to fall through to a regular LDAP bind
            if self.middleware.call_sync('ldap.has_ipa_host_keytab'):
                return DSType.IPA

        return DSType.LDAP

    def _perm_check(
        self,
        st: os.stat_result,
        expected_mode: int
    ) -> str | None:
        """
        Perform basic checks that stat security info matches expectations.
        This method is called by during health checks.

        returns a string that will be appended to error messages or None
        type if no errors found
        """
        if st.st_uid != 0:
            return f'file owned by uid {st.st_uid} rather than root.'
        if st.st_gid != 0:
            return f'file owned by gid {st.st_gid} rather than root.'

        if stat.S_IMODE(st.st_mode) != expected_mode:
            return (
                f'file permissions {oct(stat.S_IMODE(st.st_mode))} '
                f'instead of expected value of {oct(expected_mode)}.'
            )

        return None

    def check(self) -> bool:
        """
        Basic health check for directory services

        Returns:
            True if directory services enabled and healthy
            False if directory services disabled

        Raises:
            KRB5HealthError
            ADHealthError
            IPAHealthError
            LDAPHealthError
        """
        if (enabled_ds := self._get_enabled_ds()) is None:
            # Nothing is enabled and so reset values
            DSHealthObj.update(None, None, None)
            return False

        initial_status = DSHealthObj.status

        if initial_status in (DSStatus.LEAVING, DSStatus.JOINING):
            self.logger.debug("Deferring health check due to status of %s", initial_status.name)
            return True
        elif initial_status is None:
            # Our directory service hasn't been initialized.
            #
            # We'll be optimistic and call it HEALTHY before we run the
            # the actual health checks below. The reason for this is so that
            # if we attempt to etc.generate files during health check a
            # second call to directoryservices.status won't land us here again.
            DSHealthObj.update(enabled_ds, DSStatus.HEALTHY, None)

        try:
            match enabled_ds:
                case DSType.AD:
                    self._health_check_krb5()
                    self._health_check_ad()
                case DSType.IPA:
                    self._health_check_krb5()
                    self._health_check_ipa()
                case DSType.LDAP:
                    self._health_check_ldap()
                case _:
                    raise ValueError(f'{enabled_ds}: Unexpected directory service.')
        except (ADHealthError, IPAHealthError, KRB5HealthError, LDAPHealthError) as e:
            # Update our stored status to reflect reason for it being faulted
            # then re-raise
            DSHealthObj.update(enabled_ds, DSStatus.FAULTED, e.errmsg)
            raise
        except Exception:
            # Not a health related exception and so simply log it to prevent accidentally
            # disrupting services
            self.logger.error('Unexpected error while checking directory service health', exc_info=True)

        DSHealthObj.update(enabled_ds, DSStatus.HEALTHY, None)
        return True

    def recover(self, attempts=0, last_reason=None) -> None:
        """
        Attempt to recover directory services from a failed health check
        If recovery attempt fails a new exception is raised indicating current
        source of failure

        Params:
            None that should be used by API callers. This is private internal
            API for recovery attempts.

        Returns:
            None

        Raises:
            KRB5HealthError
            ADHealthError
            IPAHealthError
            LDAPHealthError
        """
        try:
            self.check()
            return
        except ADHealthError as e:
            reason = e.reason
            self._recover_ad(e)

        except IPAHealthError as e:
            reason = e.reason
            self._recover_ipa(e)

        except KRB5HealthError as e:
            reason = e.reason
            self._recover_krb5(e)

        except LDAPHealthError as e:
            reason = e.reason
            self._recover_ldap(e)

        # Perform new recovery attempt if we haven't exceeded max attempts
        # and if this isn't a repeat of the same error we had last attempt
        if attempts < MAX_RECOVER_ATTEMPTS and reason != last_reason:
            # insert a brief gap between recovery attempts
            time.sleep(1)
            return self.recover(attempts + 1, reason)

        self.check()

    def set_state(self, ds_type, ds_status, status_msg=None):
        ds = DSType(ds_type)
        status = DSStatus[ds_status]

        match status:
            case DSStatus.HEALTHY | DSStatus.JOINING | DSStatus.LEAVING:
                if status_msg is not None:
                    raise CallError('status_msg may only be set when changing state to FAULTED')
            case DSStatus.FAULTED:
                if status_msg is None:
                    raise CallError('status_msg is required when setting state to FAULTED')
            case DSStatus.DISABLED:
                DSHealthObj.update(None, None, None)
                return

        DSHealthObj.update(ds, status, status_msg)
