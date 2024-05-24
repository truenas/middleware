import base64
import json
import ldap
import os
import subprocess

from .base_interface import DirectoryServiceInterface
from .cache_mixin import CacheMixin
from .decorators import (
    active_controller,
    kerberos_ticket
)
from .kerberos_mixin import KerberosMixin
from .nsupdate_mixin import NsupdateMixin
from functools import cache
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.directoryservices import (
    ipa, ipa_constants, ldap_utils
)
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.health import (
    IPAHealthCheckFailReason,
    IPAHealthError
)
from middlewared.utils.directoryservices.ipactl_constants import (
    ExitCode,
    IpaOperation,
)
from middlewared.plugins.ldap_.ldap_client import LdapClient
from middlewared.service_exception import CallError
from typing import Optional

IPACTL = ipa_constants.IPACmd.IPACTL.value


class IpaDirectoryService(
    DirectoryServiceInterface,
    CacheMixin,
    KerberosMixin,
    NsupdateMixin,
):
    ipa_extra_config = None

    def __init__(self, middleware, is_enterprise):
        """
        We're currently layered on top of the LDAP plugin. This
        will change in future release.
        """
        super().__init__(
            middleware=middleware,
            ds_type=DSType.IPA,
            datastore_name='directoryservice.ldap',
            datastore_prefix='ldap_',
            has_sids=True,
            is_enterprise=is_enterprise,
            nss_module=NssModule.SSS.name,
            etc=['ldap', 'pam', 'nss', 'kerberos', 'ipa']
        )

    def activate(self, background_cache_fill: Optional[bool] = False) -> None:
        self.generate_etc()
        self.call_sync('service.stop', 'sssd')
        self.call_sync('service.start', 'sssd', {'silent': False})
        self.call_sync('kerberos.start')
        if background_cache_fill:
            self.call_sync('directoryservice.cache.refresh')
        else:
            self.fill_cache()

    def deactivate(self):
        self.generate_etc()
        self.call_sync('service.stop', 'sssd')
        self.call_sync('kerberos.stop')

    def is_enabled(self) -> bool:
        """
        Since we're currently layered on top of ldap plugin the
        check is only for case where we're enabled and not IPA
        """
        return self.config['enable'] and self.config['server_type'] == 'FREEIPA'

    def _parse_ipa_response(self, resp) -> dict:
        """
        ipactl returns JSON-encoded data and depending on failure
        code may also include JSON-RPC response error message from
        IPA server.
        """
        match resp.returncode:
            case ExitCode.SUCCESS:
                return json.loads(resp.stdout.decode().strip())
            case ExitCode.JSON_ERROR:
                err = resp.stderr.decode().strip()
                err_decoded = json.loads(err)
                raise CallError(err, extra=err_decoded)
            case ExitCode.NO_SMB_SUPPORT:
                err = resp.stderr.decode().strip()
                raise FileNotFoundError(err)
            case _:
                err = resp.stderr or resp.stdout
                raise RuntimeError(f'{resp.returncode}: {err.decode()}')

    def _summary_impl(self) -> dict:
        # setup_legacy just reformats the existing LDAP config
        # and so it won't fail
        domain_info = self.setup_legacy()
        domain_info.pop('username')
        try:
            domain_info |= self.get_smb_domain_info()
        except Exception:
            # The IPA domain may be unhealthy (in which case this will fail)
            # the reason why it's unhealthy will appear in the status_msg
            pass

        return {
           'type': self.name.upper(),
           'ds_status': self.status.name,
           'ds_status_str': self.status_msg,
        } | {'domain_info': domain_info}

    def setup_legacy(self) -> dict:
        """
        This is helper function for time we are wrapping around
        the LDAP table to provide IPA connectivity.
        """
        nc = self.call_sync('network.configuration.config')
        conf = self.config
        if conf['kerberos_realm']:
            realm = conf['kerberos_realm']['krb_realm']
        else:
            # No realm in ldap config and so we need to guess at it
            realm = '.'.join(
                [x.strip('dc=') for x in conf['basedn'].split(',')]
            ).upper()

        target_server = conf['hostname'].split()[0]
        if nc['domain'] != 'local':
            domain = nc['domain']
        else:
            domain = realm.lower()

        username = conf['binddn'].split(',')[0].split('=')[1]
        self.ipa_extra_config = {
            'realm': realm,
            'domain': domain,
            'host': f'{nc["hostname"]}.{realm.lower()}',
            'target_server': target_server,
            'username': username
        }

        return self.ipa_extra_config.copy()

    def insert_keytab(self, service: str, keytab_data: str) -> None:
        kt_name = f'IPA_KEYTAB_{service}'
        if kt_entry := self.call_sync('kerberos.keytab.query', [
            ['name', '=', kt_name]
        ]):
            self.call_sync(
                'datastore.update', 'directoryservice.kerberoskeytab',
                kt_entry[0]['id'],
                {'keytab_name': kt_name, 'keytab_file': keytab_data}
            )
        else:
            self.call_sync(
                'datastore.insert', 'directoryservice.kerberoskeytab',
                {'keytab_name': kt_name, 'keytab_file': keytab_data}
            )

    def setup_services(self) -> None:
        # this will generate two separate kerberos keytabs
        resp = self.set_spn(['NFS', 'SMB'])
        domain_info = None

        for entry in resp:
            self.insert_keytab(entry['spn_type'], entry['keytab'])
            if entry['spn_type'] == 'SMB':
                domain_info = entry['domain_info']

        if domain_info:
            self.call_sync('datastore.update', 'services.cifs', 1, {
                'workgroup': domain_info['netbios_name']
            })

            # We must write the password encoded in the SMB keytab
            # to secrets.tdb at this point.
            self.call_sync(
                'directoryservices.secrets.set_ipa_secret',
                base64.b64encode(domain_info['password'].encode())
            )

    @kerberos_ticket
    @active_controller
    def set_spn(self, spn_list: list) -> list:
        """
        Create service entries on remote IPA server
        """
        output = []
        for entry in set(spn_list):
            if entry not in ('SMB', 'NFS'):
                raise ValueError(f'{entry}: not a valid SPN for IPA service')

            match entry:
                case 'SMB':
                    setspn = subprocess.run([
                        IPACTL,
                        '-a', IpaOperation.SET_SMB_PRINCIPAL.name
                    ], check=False, capture_output=True)
                case 'NFS':
                    setspn = subprocess.run([
                        IPACTL,
                        '-a', IpaOperation.SET_NFS_PRINCIPAL.name
                    ], check=False, capture_output=True)
                case _:
                    raise ValueError(f'{entry}: unsupported service type')

            resp = self._parse_ipa_response(setspn)
            output.append(resp | {'spn_type': entry})

        return output

    @kerberos_ticket
    @active_controller
    def del_spn(self, spn_list: list) -> list:
        """
        Delete service entries from remote IPA server
        """
        output = []
        for entry in set(spn_list):
            if entry not in ('SMB', 'NFS'):
                raise ValueError(f'{entry}: not a valid SPN for IPA service')

            match entry:
                case 'SMB':
                    delspn = subprocess.run([
                        IPACTL,
                        '-a', IpaOperation.DEL_SMB_PRINCIPAL.name
                    ], check=False, capture_output=True)
                case 'NFS':
                    delspn = subprocess.run([
                        IPACTL,
                        '-a', IpaOperation.DEL_NFS_PRINCIPAL.name
                    ], check=False, capture_output=True)
                case _:
                    raise ValueError(f'{entry}: unsupported service type')

            resp = self._parse_ipa_response(delspn)
            output.append(resp)

        return output

    @kerberos_ticket
    @active_controller
    @cache
    def get_smb_domain_info(self):
        """
        This information shouldn't change during normal course of
        operations in a FreeIPA domain. Cache a copy of it for future
        reference.
        """
        getdom = subprocess.run([
            IPACTL, '-a', IpaOperation.SMB_DOMAIN_INFO.name,
        ], check=False, capture_output=True)

        resp = self._parse_ipa_response(getdom)
        self.ipa_smb_domain_info = resp[0] if resp else {}
        return self.ipa_smb_domain_info

    @cache
    def get_ipa_cacert(self, force=False) -> str:
        getca = subprocess.run([
            IPACTL, '-a', IpaOperation.GET_CACERT_FROM_LDAP.name,
        ], check=False, capture_output=True)

        # Second retrieve cacert and write to expected path
        # This allows us to use other IPA commands
        resp = self._parse_ipa_response(getca)
        self.ipa_cacert = resp['cacert']
        return self.ipa_cacert

    def _join_impl(self, host: str, domain: str, realm: str, server: str) -> dict:
        # First write our freeipa config (this allows us to get our cert)
        ipa.write_ipa_default_config(host, domain, realm, server)

        ipa_cacert = self.get_ipa_cacert(True)
        ipa.write_ipa_cacert(ipa_cacert.encode())

        # Now we should be able to join
        join = subprocess.run([
            IPACTL, '-a', IpaOperation.JOIN.name
        ], check=False, capture_output=True)
        resp = self._parse_ipa_response(join)
        resp['cacert'] = ipa_cacert

        return resp

    def _drop_config(self) -> None:
        """
        This method is private and intended only to be used within
        context of rolling back an in-progress IPA join and forcibly
        clearing state after leaving IPA
        """
        return
        for p in (
            ipa_constants.IPAPath.DEFAULTCONF.path,
            ipa_constants.IPAPath.CACERT.path
        ):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass

    @kerberos_ticket
    @active_controller
    def join(
        self,
        host: str,
        domain: str,
        realm: str,
        server: str
    ) -> dict:
        """
        Join IPA domain returns dictionary containing the following:

        `cacert` - base64-encoded cacert for the IPA domain

        `keytab` - base64-encoded keytab for the newly-created host principal
        for this server

        `result` - dictionary containing full JSON-rpc response from IPA server

        Prior to calling this method the following _must_ be configured:
        - krb5.conf
        - valid administrative kerberos ticket for IPA domain

        After calling this method we will have:
        - valid /etc/ipa/default.conf file
        - correct cacert _temporarily_ written to /etc/ipa/ca.crt

        Required post-join steps will be
        - write host keytab to datastore
        - write cacert to datastore
        - add services (NFS / SMB)
        - configure sssd, openldap, smb, etc
        """
        try:
            data = self._join_impl(host, domain, realm, server)
        except Exception as e:
            self._drop_config()
            raise e from None

        return data

    @kerberos_ticket
    @active_controller
    def leave(self) -> dict:
        """
        Leave IPA domain. This requires valid administrator kerberos
        ticket.

        This only performs server-side operations on IPA server. No
        changes are written to TrueNAS server.
        """
        leave = subprocess.run([
            IPACTL, '-a', IpaOperation.LEAVE.name
        ], check=False, capture_output=True)

        return self._parse_ipa_response(leave)

    def _health_check_impl(self) -> None:
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
