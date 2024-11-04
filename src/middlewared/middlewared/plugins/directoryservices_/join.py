import ipaddress

from .activedirectory_join_mixin import ADJoinMixin
from .ipa_join_mixin import IPAJoinMixin
from .ldap_join_mixin import LDAPJoinMixin
from middlewared.job import Job
from middlewared.plugins.ldap_.constants import SERVER_TYPE_FREEIPA
from middlewared.service import job, Service
from middlewared.service_exception import CallError
from middlewared.utils.directoryservices.constants import DomainJoinResponse, DSType
from middlewared.utils.directoryservices.krb5 import kerberos_ticket
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
        dstype = self.midleware.call_sync('directoryservices.config')['dstype']
        return DSType(dstype)

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
        This method performs DNS update via GSS-TSIG using middlewared's current kerberos credential
        and should only be called within the context initially joining the domain. In the future
        this can be enhanced to be a periodic job that can also perform dynamic DNS updates.

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
        if not isinstance(fqdn, str):
            raise TypeError(f'{type(fqdn)}: must be a string')
        elif dot not in fqdn:
            raise ValueError(f'{fqdn}: missing domain component of name')

        ds_type_str = self.middleware.call_sync('directoryservices.status')['type']
        match ds_type_str:
            case DSType.AD.value | DSType.IPA.value:
                pass
            case None:
                raise CallError('Directory services must be enabled in order to register DNS')
            case _:
                raise CallError(f'{ds_type_str}: directory service type does not support DNS registration')

        if fqdn.startswith('localhost'):
            raise CallError(f'{fqdn}: Invalid domain name.')

        if not fqdn.endswith(dot):
            fqdn += dot

        payload = self._create_nsupdate_payload(fqdn, 'ADD', do_ptr)
        self.middleware.call_sync('dns.nsupdate', {'ops': payload})

    @kerberos_ticket
    def unregister_dns(self, fqdn: str, do_ptr: bool = False):
        if not isinstance(fqdn, str):
            raise TypeError(f'{type(fqdn)}: must be a string')
        elif dot not in fqdn:
            raise ValueError(f'{fqdn}: missing domain component of name')

        ds_type_str = self.middleware.call_sync('directoryservices.status')['type']
        match ds_type_str:
            case DSType.AD.value | DSType.IPA.value:
                pass
            case None:
                raise CallError('Directory services must be enabled in order to unregister DNS')
            case _:
                raise CallError(f'{ds_type_str}: directory service type does not support DNS registration')

        if fqdn.startswith('localhost'):
            raise CallError(f'{fqdn}: Invalid domain name.')

        if not fqdn.endswith(dot):
            fqdn += dot

        payload = self._create_nsupdate_payload(fqdn, 'DELETE', do_ptr)
        self.middleware.call_sync('dns.nsupdate', {'ops': payload})

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
                    f'{ds_type}: specified directory service type does not '
                    'support domain join functionality.'
                )

        return is_joined_fn(ds_type, domain)

    def join_status(self, ds_type_str: DSType, ds_config: dict) -> DomainJoinResponse:
        """ External method to check whether we need to perform a domain join

        Args:
            ds_type: Type of directory service that is being tested. Choices
                are DSType.AD and DSType.IPA
            ds_config: `configuration` key from directoryservices.config output 

        Returns:
            DomainJoinResponse

        Raises:
            CallError
            TypeError
        """
        ds_type = DSType(ds_type_str)

        match ds_type:
            case DSType.AD | DSType.IPA:
                if self._test_is_joined(ds_type, ds_config['domainname'])
                    return DomainJoinResponse.ALREADY_JOINED
                else:
                    return DomainJoinResponse.NOT_JOINED
            case DSType.LDAP | DSType.STANDALONE:
                # There is no real join process for openldap server
                # and so just respond we're already joined.
                return DomainJoinResponse.ALREADY_JOINED
            case _:
                raise CallError(f'{ds_type}: unknown DSType')

    @job(lock="directoryservices_join_leave")
    @kerberos_ticket
    def join_domain(
        self, job: Job,
        ds_type_str: str,
        domain: str,
        force: bool = False
    ) -> DomainJoinResponse:
        """ Join an IPA or active directory domain

        Create TrueNAS account on remote domain controller (DC) and clean
        update TrueNAS configuration to reflect settings determined during
        the join process. Requires a valid kerberos ticket for a privileged
        account on the domain because we performing operations on the DC.

        If join fails then TrueNAS will attempt to roll back changes to a
        clean state.

        Args:
            ds_type_str: String value of the DSType to be joined. Supported
                values are 'ACTIVEDIRECTORY' and 'IPA'
            domain: Name of domain to be joined. For AD domains this should
                be the pre-win2k domain, and for IPA domains the kerberos
                realm.
            force: Skip the step where we check whether TrueNAS is already
                joined to the domain. Join should not be forced without very
                good reason as this will cause auditing events on the domain
                controller and may disrupt services on the TrueNAS server.

        Returns:
            str - One of DomainJoinResponse strings

        Raises:
            ValueError - ds_type_str is an invalid DSType
        """

        ds_type = DSType(ds_type_str)

        if not force:
            if self._test_is_joined(ds_type, domain):
                self.logger.debug(
                    '%s: server is already joined to domain %s',
                    ds_type_str, domain
                )
                return DomainJoinResponse.ALREADY_JOINED.value

        match ds_type:
            case DSType.AD:
                do_join_fn = self._ad_join
            case DSType.IPA:
                do_join_fn = self._ipa_join
            case _:
                raise CallError(
                    f'{ds_type}: specified directory service type does not '
                    'support domain join functionality.'
                )

        do_join_fn(job, ds_type, domain)
        return DomainJoinResponse.PERFORMED_JOIN.value

    def grant_privileges(self, ds_type_str: str, domain: str) -> None:
        ds_type = DSType(ds_type_str)

        if not self._test_is_joined(ds_type, domain):
            raise CallError('TrueNAS is not joined to domain')

        match ds_type:
            case DSType.AD:
                self._ad_grant_privileges()
            case DSType.IPA:
                self._ipa_grant_privileges()
            case _:
                raise ValueError(f'{ds_type}: unexpected directory sevice type')

    @job(lock="directoryservices_join_leave")
    @kerberos_ticket
    def leave_domain(self, job: Job, ds_type_str: str, domain: str) -> None:
        """ Leave an IPA or active directory domain

        Remove TrueNAS configuration from remote domain controller (DC) and clean
        up local configuration. Requires a valid kerberos ticket for a privileged
        account on the domain because we performing operations on the DC.

        Args:
            ds_type_str: String value of the DSType to be left. Supported
                values are 'ACTIVEDIRECTORY' and 'IPA'
            domain: Name of domain to be left. For AD domains this should
                be the pre-win2k domain, and for IPA domains the kerberos
                realm.

        Returns:
            None

        Raises:
            ValueError - ds_type_str is an invalid DSType
        """

        ds_type = DSType(ds_type_str)

        match ds_type:
            case DSType.AD:
                do_leave_fn = self._ad_leave
            case DSType.IPA:
                do_leave_fn = self._ipa_leave
            case _:
                raise CallError(
                    f'{ds_type}: specified directory service type does not '
                    'support domain join functionality.'
                )

        # Only make actual attempt to leave the domain if we have a valid join
        if self._test_is_joined(ds_type, domain):
            do_leave_fn(job, ds_type, domain)
        else:
            self.logger.warning(
                '%s: domain join is not healthy. Manual cleanup of machine account on '
                'remote domain controller for domain may be required.', domain
            )

        # TODO move cleanup methods here
