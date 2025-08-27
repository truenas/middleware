import errno
import ipaddress

from .activedirectory_join_mixin import ADJoinMixin
from .ipa_join_mixin import IPAJoinMixin
from .ldap_join_mixin import LDAPJoinMixin
from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.job import Job
from middlewared.service import job, pass_app, Service
from middlewared.service_exception import CallError
from middlewared.utils.directoryservices.common import ds_config_to_fqdn
from middlewared.utils.directoryservices.constants import DomainJoinResponse, DSStatus, DSType
from middlewared.utils.directoryservices.dns import (
    NSUPDATE_LOCK, dns_record_is_expired, update_dns_record_state, remove_dns_record_state
)
from middlewared.utils.directoryservices.krb5 import kerberos_ticket, kdc_saf_cache_set
from middlewared.utils.tdb import close_sysdataset_tdb_handles
from os import curdir as dot


class DomainConnection(
    Service,
    ADJoinMixin,
    IPAJoinMixin,
    LDAPJoinMixin,
):

    class Config:
        namespace = 'directoryservices.connection'
        cli_private = True
        private = True

    def _get_enabled_ds(self):
        server_type = self.middleware.call_sync('directoryservices.config')['service_type']
        return DSType(server_type)

    @pass_app()
    def deactivate_standby(self, app, service_type) -> None:
        if app and not isinstance(app.authenticated_credentials, TruenasNodeSessionManagerCredentials):
            raise CallError(f'{type(app.authenticated_credentials)}: unexpected credential type for endpoint.')

        if self.middleware.call_sync('failover.is_single_master_node'):
            self.logger.warning('deactivate_standby() called on controller that is not standby.')
            return

        ds_type = DSType(service_type)
        self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.DISABLED.name)
        self.middleware.call_sync('kerberos.stop')
        for etc_file in ds_type.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

    @pass_app()
    def activate_standby(self, app, kdc_affinity) -> None:
        """ Activate the standby controller. This should be called through failover.call_remote. This
        should be used after successfully setting up directory services on the active controller. """
        if app and not isinstance(app.authenticated_credentials, TruenasNodeSessionManagerCredentials):
            raise CallError(f'{type(app.authenticated_credentials)}: unexpected credential type for endpoint.')

        if self.middleware.call_sync('failover.is_single_master_node'):
            self.logger.warning('activate_standby() called on controller that is not standby.')
            return

        if kdc_affinity:
            kdc_saf_cache_set(kdc_affinity)

        # This is largely the same as normal `activate()` with addition of clearing local caches
        # and replacing state file (secrets.tdb).

        close_sysdataset_tdb_handles()
        match (enabled_ds := self._get_enabled_ds()):
            case None:
                self.logger.debug('activate_standby() called on controller that is not joined to a'
                                  'directory service.')
                return
            case DSType.IPA:
                self.middleware.call_sync('directoryservices.secrets.restore')
                activate_fn = self._ipa_activate
            case DSType.AD:
                self.middleware.call_sync('directoryservices.secrets.restore')
                activate_fn = self._ad_activate
            case DSType.LDAP:
                activate_fn = self._ldap_activate
            case _:
                raise ValueError(f'{enabled_ds}: unknown directory service')

        try:
            activate_fn()
        except Exception:
            # We'll squash the exception here since we may still have some hope of recovery in
            # next call
            self.logger.warning('%s: failed to activate directory service', enabled_ds, exc_info=True)

        try:
            self.middleware.call_sync('directoryservices.health.recover')
        except Exception:
            self.logger.warning('Failed to become healthy on standby controller', exc_info=True)

    def activate(self) -> int:
        """ Generate etc files and start services, then start cache fill job and return job id """
        match (enabled_ds := self._get_enabled_ds()):
            case None:
                return
            case DSType.IPA:
                self._ipa_activate()
            case DSType.AD:
                self._ad_activate()
            case DSType.LDAP:
                self._ldap_activate()
            case _:
                raise ValueError(f'{enabled_ds}: unknown directory service')

        return self.middleware.call_sync('directoryservices.cache.refresh_impl').id

    def _create_nsupdate_payload(self, fqdn: str, cmd_type: str, do_ptr: bool = False):
        if fqdn.startswith('localhost'):
            raise CallError(f'{fqdn}: Invalid domain name.')

        if not fqdn.endswith(dot):
            fqdn += dot

        payload = []
        if self.middleware.call_sync('failover.licensed'):
            master, backup, init = self.middleware.call_sync('failover.vip.get_states')
            for master_iface in self.middleware.call_sync('interface.query', [["id", "in", master + backup]]):
                for i in master_iface['failover_virtual_aliases']:
                    addr = ipaddress.ip_address(i['address'])
                    payload.append({
                        'command': cmd_type,
                        'name': fqdn,
                        'address': str(addr),
                        'do_ptr': do_ptr,
                        'type': 'A' if addr.version == 4 else 'AAAA'
                    })
        else:
            for i in self.middleware.call_sync('interface.ip_in_use'):
                addr = ipaddress.ip_address(i['address'])
                payload.append({
                    'command': cmd_type,
                    'name': fqdn,
                    'address': str(addr),
                    'do_ptr': do_ptr,
                    'type': 'A' if addr.version == 4 else 'AAAA'
                })

        return payload

    @kerberos_ticket
    def register_dns(self, fqdn: str, do_ptr: bool = False):
        """
        This method performs DNS update via GSS-TSIG using middlewared's current kerberos credential.

        Args:
            `fqdn` - should be the fully qualified domain name of the TrueNAS server.

            `do_ptr` - set associated PTR record when registering fqdn. Not all domains will
            have a reverse zone configured and so detection should be done prior to calling
            this method.

        Returns:
            None

        Raises:
            TypeError
            ValueError
            CallError
        """
        with NSUPDATE_LOCK:
            if not isinstance(fqdn, str):
                raise TypeError(f'{type(fqdn)}: must be a string')
            elif dot not in fqdn:
                raise ValueError(f'{fqdn}: missing domain component of name')

            ds_config = self.middleware.call_sync('directoryservices.config')
            if not ds_config['enable']:
                raise CallError('Directory services must be enabled in order to register DNS')

            if not ds_config['enable_dns_updates']:
                raise CallError('DNS updates are disabled for the directory service')

            ds_type_str = ds_config['service_type']
            match ds_type_str:
                case DSType.AD.value | DSType.IPA.value:
                    pass
                case _:
                    raise CallError(f'{ds_type_str}: directory service type does not support DNS registration')

            if fqdn.startswith('localhost'):
                raise CallError(f'{fqdn}: Invalid domain name.')

            if not fqdn.endswith(dot):
                fqdn += dot

            payload = self._create_nsupdate_payload(fqdn, 'ADD', do_ptr)
            self.middleware.call_sync('dns.nsupdate', {'ops': payload})
            update_dns_record_state(fqdn)

    def renew_dns(self):
        """
        Perform automatic renewal of our expected DNS records through nsupdate / GSS-TSIG using the
        current kerberos credential.
        """
        with NSUPDATE_LOCK:
            ds_config = self.middleware.call_sync('directoryservices.config')
            if not ds_config['enable'] or not ds_config['enable_dns_updates']:
                # Server isn't configured for updates
                return

            if not ds_config['kerberos_realm']:
                # We use GSS-TSIG for updates. We can't do this if kerberos isn't configured
                raise RuntimeError('Unable to perform DNS update due to missing kerberos realm')

            if not self.middleware.call_sync('failover.is_single_master_node'):
                # We don't want standby controller trying to do nsupdate
                return

            sysdataset = self.middleware.call_sync('systemdataset.config')
            if not sysdataset['path']:
                # Our expected system dataset pool is not actually mounted. This is problematic
                # for DNS updates because we store some state about last time we attempted to
                # nsupdate there.
                raise FileNotFoundError(f'{sysdataset["basename"]}: system dataset not mounted')

            # This check has to happen after system dataset because the state file is stored
            # on the system dataset.
            fqdn = ds_config_to_fqdn(ds_config)
            if not dns_record_is_expired(fqdn):
                return

            # generate a renew payload. Currently we are only doing ptr updates on AD.
            # We are not deleting any old / incorrect entries. At least in AD case the outdated
            # entries will be scavenged within a week or so.
            payload = self._create_nsupdate_payload(fqdn, 'ADD', ds_config['service_type'] == DSType.AD.value)
            self.middleware.call_sync('dns.nsupdate', {'ops': payload})
            update_dns_record_state(fqdn)

    @kerberos_ticket
    def unregister_dns(self, fqdn: str, do_ptr: bool = False):
        with NSUPDATE_LOCK:
            if not isinstance(fqdn, str):
                raise TypeError(f'{type(fqdn)}: must be a string')
            elif dot not in fqdn:
                raise ValueError(f'{fqdn}: missing domain component of name')

            ds_config = self.middleware.call_sync('directoryservices.config')
            if not ds_config['enable']:
                raise CallError('Directory services must be enabled in order to deregister DNS')

            ds_type_str = ds_config['service_type']
            match ds_type_str:
                case DSType.AD.value | DSType.IPA.value:
                    pass
                case _:
                    raise CallError(f'{ds_type_str}: directory service type does not support DNS unregistration')

            if fqdn.startswith('localhost'):
                raise CallError(f'{fqdn}: Invalid domain name.')

            if not fqdn.endswith(dot):
                fqdn += dot

            payload = self._create_nsupdate_payload(fqdn, 'DELETE', do_ptr)
            self.middleware.call_sync('dns.nsupdate', {'ops': payload})
            remove_dns_record_state()

    @kerberos_ticket
    def _test_is_joined(self, ds_type: DSType, domain: str) -> bool:
        """ Test to see whether TrueNAS is already joined to the domain

        Args:
            ds_type: Type of directory service that is being tested. Choices
                are DSType.AD and DSType.IPA
            domain: Name of domain to be joined. For AD domains this should
                be the pre-win2k domain, and for IPA domains the kerberos
                realm.

        Returns:
            True - joined to domain
            False - not joined to domain

        Raises:
            CallError
            TypeError
        """
        if not isinstance(ds_type, DSType):
            raise TypeError(f'{type(ds_type)}: DSType is required')

        match ds_type:
            case DSType.AD:
                is_joined_fn = self._ad_test_join
            case DSType.IPA:
                is_joined_fn = self._ipa_test_join
            case _:
                raise CallError(
                    f'{ds_type}: The configured directory service type does not support joining a domain.',
                    errno.EOPNOTSUPP
                )

        return is_joined_fn(domain)

    @job(lock="directoryservices_join_leave")
    @kerberos_ticket
    def join_domain(self, job: Job, force: bool = False) -> None:
        """ Join an IPA or active directory domain

        Create TrueNAS account on remote domain controller (DC) and
        update TrueNAS configuration to reflect settings determined during
        the join process. Requires a valid kerberos ticket for a privileged
        account on the domain because we performing operations on the DC.

        If join fails then TrueNAS will attempt to roll back changes to a
        clean state.

        Args:
            force: Skip the step where we check whether TrueNAS is already
                joined to the domain. Join should not be forced without very
                good reason as this will cause auditing events on the domain
                controller and may disrupt services on the TrueNAS server.

        Returns:
            str - One of DomainJoinResponse strings
        """

        ds_config = self.middleware.call_sync('directoryservices.config')
        ds_type = DSType(ds_config['service_type'])
        domain = ds_config['configuration']['domain']

        if not force:
            if self._test_is_joined(ds_type, domain):
                self.logger.debug(
                    '%s: server is already joined to domain %s',
                    ds_type, domain
                )
                return DomainJoinResponse.ALREADY_JOINED.value

        match ds_type:
            case DSType.AD:
                do_join_fn = self._ad_join
            case DSType.IPA:
                do_join_fn = self._ipa_join
            case _:
                raise CallError(
                    f'{ds_type}: The configured directory service type does not support joining a domain.',
                    errno.EOPNOTSUPP
                )

        do_join_fn(job, ds_config)
        return DomainJoinResponse.PERFORMED_JOIN.value

    def grant_privileges(self, ds_type_str: str, domain: str) -> None:
        ds_type = DSType(ds_type_str)

        if not self._test_is_joined(ds_type, domain):
            raise CallError('TrueNAS is not joined to domain')

        match ds_type:
            case DSType.AD:
                self._ad_grant_privileges(domain)
            case DSType.IPA:
                self._ipa_grant_privileges(domain)
            case _:
                raise ValueError(f'{ds_type}: unexpected directory sevice type')

    def remove_privileges(self, domain: str) -> None:
        if not (priv := self.middleware.call_sync('privilege.query', [['name', '=', domain]])):
            return

        if priv[0]['local_groups']:
            self.logger.warning('%s: cannot remove the RBAC privilege for the domain because '
                                'local accounts use the privilege.', domain)
            return

        self.middleware.call_sync('privilege.delete', priv[0]['id'])

    @job(lock="directoryservices_join_leave")
    @kerberos_ticket
    def leave_domain(self, job: Job) -> None:
        """ Leave an IPA or active directory domain

        Remove TrueNAS configuration from remote domain controller (DC) and clean
        up local configuration. Requires a valid kerberos ticket for a privileged
        account on the domain because we performing operations on the DC.

        Args:
            None

        Returns:
            None

        Raises:
            CallError - directory service does not support join / leave operations.
                        errno will be set to EOPNOTSUPP
            CallError - the current domain join is not healthy. Configuration was automatically
                        cleared. errno will be set to EFAULT
        """

        ds_config = self.middleware.call_sync('directoryservices.config')
        ds_type = DSType(ds_config['service_type'])

        match ds_type:
            case DSType.AD:
                do_leave_fn = self._ad_leave
                do_cleanup_fn = self._ad_cleanup
            case DSType.IPA:
                do_leave_fn = self._ipa_leave
                do_cleanup_fn = self._ipa_cleanup
            case _:
                raise CallError(
                    f'{ds_type}: The configured directory service type does not support leaving a domain.',
                    errno.EOPNOTSUPP
                )

        domain = ds_config['configuration']['domain']
        self.remove_privileges(domain)
        # Only make actual attempt to leave the domain if we have a valid join
        if self._test_is_joined(ds_type, domain):
            do_leave_fn(job, ds_config)
        else:
            # There's not much we can do to recover from this and so we'll just rip out old configuration
            # server-side and complain to admin that they may need to clean up.
            do_cleanup_fn(job, ds_config)
            raise CallError(
                f'{domain}: The domain join is not healthy. This prevents the TrueNAS server from leaving the domain. '
                'You may need to manually clean up the machine account on the remote domain controller.'
            )
