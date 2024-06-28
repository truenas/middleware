import os
import stat

from .activedirectory_health_mixin import ADHealthMixin
from .ipa_health_mixin import IPAHealthMixin
from .kerberos_health_mixin import KerberosHealthMixin
from middlewared.plugins.ldap_.constants import SERVER_TYPE_FREEIPA
from middlewared.service import Service
from middlewared.service_exception import CallError
from middlewared.utils.directoryservices.constants import DSStatus, DSType
from middlewared.utils.directoryservices.health import (
    ADHealthError, DSHealthObj, IPAHealthError, KRB5HealthError,
    LDAPHealthError
)


class DomainHealth(
    Service,
    ADHealthMixin,
    IPAHealthMixin,
    KerberosHealthMixin,
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

        return DSType.IPA if ldap['ldap_server_type'] == SERVER_TYPE_FREEIPA else DSType.LDAP

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

    def recover(self):
        """
        Attempt to recover directory services from a failed health check
        If recovery attempt fails a new exception is raised indicating current
        source of failure

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
            self._recover_ad(e)

        except IPAHealthError as e:
            self._recover_ipa(e)

        except KRB5HealthError as e:
            self._recover_krb5(e)

        except LDAPHealthError as e:
            self._recover_ldap(e)

        # hopefully this fixed the issue
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
                # Only change current state if the specified DS matches
                # our current running configuration
                current_ds = DSHealthObj.dstype
                if ds is current_ds:
                    DSHealthObj.update(None, None, None)

                return

        DSHealthObj.update(ds, status, status_msg)
