import os
import subprocess
import wbclient

from .activedirectory_health_mixin import ADHealthMixin
from .base_interface import DirectoryServiceInterface
from .cache_mixin import CacheMixin
from .decorators import (
    active_controller,
    ttl_cache,
    kerberos_ticket,
)
from .kerberos_mixin import KerberosMixin
from .nsupdate_mixin import NsupdateMixin
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.directoryservices.ad import (
    get_domain_info,
    get_machine_account_status,
    lookup_dc
)
from middlewared.utils.directoryservices.constants import (
    DSType, DSStatus
)
from middlewared.utils.directoryservices.health import (
    ADHealthError,
    KRB5HealthError,
)
from middlewared.utils.directoryservices.krb5_constants import (
    krb5ccache
)
from middlewared.plugins.smb_.constants import SMBCmd, SMBPath
from middlewared.service_exception import CallError, MatchNotFound
from time import time
from typing import Optional


class ADDirectoryService(
    DirectoryServiceInterface,
    CacheMixin,
    KerberosMixin,
    NsupdateMixin,
    ADHealthMixin
):

    def __init__(self, middleware, is_enterprise):
        super().__init__(
            middleware=middleware,
            ds_type=DSType.AD,
            datastore_name='directoryservice.activedirectory',
            datastore_prefix='ad_',
            has_sids=True,
            has_dns_update=True,
            is_enterprise=is_enterprise,
            nss_module=NssModule.WINBIND.name,
            etc=['pam', 'nss', 'smb', 'kerberos']
        )

    def _cache_online_check(self) -> bool:
        """
        This method gets called via a CacheMixin method during cache fill to
        wait for the domain to come properly online.
        """
        offline_domains = self.call_sync(
            'idmap.online_status',
            [['online', '=', False]]
        )
        if offline_domains:
            self.logger.debug(
                'Waiting for the following domains to come online: %s.',
                ', '.join([x['domain'] for x in offline_domains])
            )

        return not offline_domains

    def _cache_dom_sid_info(self) -> dict:
        """
        This overrides the _cache_dom_sid_info() method provided by CacheMixin
        and provides idmap configuration for trusted domains which is
        then used to synthesize stable `id` values for when user.query
        and group.query return entries from directory services.
        """
        domain_info = self.call_sync(
            'idmap.query',
            [["domain_info", "!=", None]],
            {'extra': {'additional_information': ['DOMAIN_INFO']}}
        )
        return {dom['domain_info']['sid']: dom for dom in domain_info}

    def _get_fqdn(self) -> str:
        """ Retrieve server hostname for DNS register / unregister """
        smb_conf = self.call_sync('smb.config')
        conf = self.config
        return f'{smb_conf["netbiosname"]}.{conf["domainname"]}.'

    def _domain_info(
        self,
        domain_in: Optional[str] = None,
        retry: Optional[bool] = True
    ) -> dict:
        """
        Use libads to query information about the specified domain.
        If it is left unspecifed then the value of `domainname` in the
        AD configuration will be used.

        See get_domain_info() documentation for keys and expected values
        """
        domain = domain_in or self.config['domainname']
        try:
            domain_info = get_domain_info(domain)
        except Exception as e:
            if not retry:
                raise e from None

            # samba's gencache may have a stale server affinity entry
            # or stale negative cache results
            self.call_sync('idmap.gencache.flush')
            domain_info = get_domain_info(domain)

        return domain_info

    def _lookup_dc(
        self,
        domain_in: Optional[str] = None,
        retry: Optional[bool] = True
    ) -> dict:
        """
        Look up some basic information about the domain controller that
        is currently set in the libads server affinity cache.
        """
        domain = domain_in or self.config['domainname']
        try:
            dc_info = lookup_dc(domain)
        except Exception as e:
            if not retry:
                raise e from None

            # samba's gencache may have a stale server affinity entry
            # or stale negative cache results
            self.call_sync('idmap.gencache.flush')
            dc_info = lookup_dc(domain)

        return dc_info

    @kerberos_ticket
    @active_controller
    def test_join(self, workgroup: str):
        """
        Test to see whether we're currently joined to an AD domain.
        """
        netads = subprocess.run([
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-w', workgroup,
            '-d', '5',
            'ads', 'testjoin'
        ], check=False, capture_output=True)

        if netads.returncode == 0:
            return True

        err_msg = netads.stderr.decode()
        log_path = f'{SMBPath.LOGDIR.platform()}/domain_testjoin_{time()}.log'
        with open(log_path, 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(err_msg)
            f.flush()

        # We only want to forcible rejoin active directory if it's clear
        # that our credentials are wrong or the computer account doesn't
        # exist
        for err_str in (
            'join to domain is not valid',
            '0xfffffff6',
            'LDAP_INVALID_CREDENTIALS',
            'The name provided is not a properly formed account name',
            'The attempted logon is invalid.'
        ):
            if err_str in err_msg:
                return False

        raise CallError(
            'Attempt to check AD join status failed unexpectedly. '
            f'Please review logs at {log_path} and file a bug report.'
        )

    def activate(self, background_cache_fill: Optional[bool] = False) -> None:
        """
        Activate our bind to active directory. This may be called currently
        from the AD plugin or from `directoryservices.become_active`.
        """
        self.generate_etc()
        self.call_sync('service.stop', 'idmap')
        self.call_sync('service.start', 'idmap', {'silent': False})
        self.call_sync('kerberos.start')
        if background_cache_fill:
            # background job to rebuild the UI / middleware cache
            self.call_sync('directoryservices.cache.refresh')
        else:
            self.fill_cache()
        self.call_sync('alert.run_source', 'ActiveDirectoryDomainBind')

    def deactivate(self) -> None:
        """
        Deactivate our domain bind. This may be called when we are stopping the
        AD service or when `directoryservices.become_passive` is called.
        """
        self.generate_etc()
        self.call_sync('service.restart', 'idmap')
        self.call_sync('kerberos.stop')

    def _do_post_join_actions(self, force: bool):
        self.register_dns(force)

        # set NFS SPN. This also forces write to our keytabs DB
        self.set_spn(['nfs'])

        # The password in secrets.tdb has been replaced so make
        # sure we have it backed up in our config.
        self.call_sync('directoryservices.secrets.backup')

        # Force an update to stale cache
        dom_info = self._summary_domain_info(ttl_cache_refresh=True)
        self.activate()

        """
        # regenerate our config files now that we're joined to AD.
        self.generate_etc()

        # restart winbindd so that running configuration is definitely
        # correct
        self.call_sync('service.restart', 'idmap')

        # Filling our cache forces wait until winbind considers itself online
        self.fill_cache()
        """
        # get our domain from winbind
        dom = wbclient.Ctx().domain()

        existing_privileges = self.call_sync(
            'privilege.query',
            [["name", "=", dom.dns_name.upper()]]
        )

        # By this point we are healthy and can set our status as such
        self.status = DSStatus.HEALTHY.name

        if not existing_privileges:
            # grant the domain admins group full admin rights to NAS
            try:
                self.call_sync('privilege.create', {
                    'name': dom.dns_name.upper(),
                    'ds_groups': [f'{dom.sid}-512'],
                    'allowlist': [{'method': '*', 'resource': '*'}],
                    'web_shell': True
                })
            except Exception:
                self.logger.warning(
                    "Failed to grant domain administrators access to "
                    "TrueNAS API.", exc_info=True
                )

        return dom_info

    @kerberos_ticket
    @active_controller
    def join(self, workgroup: str, force: Optional[bool] = False) -> dict:
        """
        Join an active directory domain. Requires admin kerberos ticket.
        If post-join operations fail, then we attempt to roll back changes on
        the DC.
        """
        conf = self.config

        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-U', conf['bindname'],
            '-d', '5',
            'ads', 'join',
        ]

        if conf['createcomputer']:
            cmd.append(f'createcomputer={conf["createcomputer"]}')

        cmd.extend([
            '--no-dns-updates', conf['domainname']
        ])

        netads = subprocess.run(cmd, check=False, capture_output=True)
        if netads.returncode != 0:
            err_msg = netads.stderr.decode().split(':', 1)[1]
            raise CallError(err_msg)

        # we've now successfully joined AD and can proceed with post-join
        # operations
        try:
            return self._do_post_join_actions(force)
        except Exception as e:
            # We failed to set up DNS / keytab cleanly
            # roll back and present user with error
            self.leave(conf['bindname'])
            self.call_sync('idmap.gencache.flush')
            raise e from None

    def _post_leave(self):
        config = self.config

        # try to unregister our DNS entries
        try:
            self.unregister_dns()
        except Exception:
            self.logger.warning(
                'Failed to clean up DNS entries. Further action may be required '
                'by an Active Directory administrator.', exc_info=True
            )

        if krb_princ := self.call_sync('kerberos.keytab.query', [
            ('name', '=', 'AD_MACHINE_ACCOUNT')
        ]):
            self.call_sync(
                'datastore.delete',
                'directoryservice.kerberoskeytab',
                krb_princ[0]['id']
            )

        if config['kerberos_realm']:
            try:
                self.call_sync(
                    'datastore.delete',
                    'directoryservice.kerberosrealm',
                    config['kerberos_realm']['id']
                )
            except MatchNotFound:
                pass

        try:
            self.call_sync('directoryservices.secrets.backup')
        except Exception:
            self.logger.debug("Failed to remove stale secrets entries.", exc_info=True)

        # reset our config
        self.call_sync('datastore.update', self._datastore_name, config['id'], {
            'enable': False,
            'site': None,
            'bindname': '',
            'kerberos_realm': None,
            'kerberos_principal': '',
            'domainname': '',
        }, {'prefix': self._datastore_prefix})
        self.update_config()
        self.status = DSStatus.DISABLED.name

        # Clean up privileges
        existing_privileges = self.call_sync('privilege.query', [
            ["name", "=", config['domainname']]
        ])
        if existing_privileges:
            self.call_sync('privilege.delete', existing_privileges[0]['id'])

        self.generate_etc()
        self.call_sync('idmap.gencache.flush')
        self.call_sync('service.restart', 'idmap')

    @kerberos_ticket
    @active_controller
    def leave(self, username: str) -> None:
        """ Delete our computer object from active directory """
        self.status = DSStatus.LEAVING.name
        netads = subprocess.run([
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-U', username,
            'ads', 'leave',
        ], check=False, capture_output=True)

        # remove cached machine account information
        if netads.returncode != 0:
            self.logger.warning(
                'Failed to cleanly leave domain. Further action may be required '
                'by an Active Directory administrator: %s', netads.stderr.decode()
            )

        self._post_leave()

    @ttl_cache()
    def _summary_domain_info(self) -> dict:
        domain_info = self._domain_info()

        # since this is cached we don't want to store the time as reported by
        # the domain controller. domain_info also contains reports on clock
        # slew via `server_time_offset` key
        domain_info.pop('server_time')

        machine_account = get_machine_account_status(
            domain_info['ldap_server']
        )
        machine_account['last_password_change'] = domain_info.pop('last_machine_account_password_change')

        dc_info = lookup_dc(
            domain_info['ldap_server']
        )

        # select only keys we want from `lookup dc` response.
        output = {
            'forest': dc_info['forest'],
            'domain': dc_info['domain'],
            'pre-win2k_domain': dc_info['pre-win2k_domain'],
            'domain_contoller': dc_info['domain_controller'],
            'domain_contoller_address': dc_info['information_for_domain_controller'],
            'domain_controller_site': dc_info['server_site_name'],
        } | domain_info
        output['machine_account'] = machine_account

        return output

    def _recover_impl(self) -> None:
        try:
            self.health_check()
            self.status = DSStatus.HEALTHY.name
            return
        except KRB5HealthError as e:
            self._recover_krb5(e)
        except ADHealthError as e:
            self._recover_ad(e)

        # Hopefully this has fixed the issue
        self.health_check()

    def _summary_impl(self) -> dict:
        """ provide basic summary of AD status """
        self._assert_is_active()

        domain_info = None
        if self.status is DSStatus.HEALTHY:
            try:
                domain_info = self._summary_domain_info()
            except Exception:
                self.logger.warning('Failed to retrieve domain information', exc_info=True)

        return {
            'type': self.name.upper(),
            'status': self.status.name,
            'status_msg': self.status_msg,
            'domain_info': domain_info
        }

    @kerberos_ticket
    @active_controller
    def set_spn(self, spn_list: list) -> None:
        """
        Create service entries on domain controller and update our
        stored kerberos keytab to reflect them. Currently only NFS
        is supported, but we may expand this in the future.
        """
        for service in spn_list:
            if service not in ('nfs'):
                raise ValueError(f'{service}: not a supported service')

            cmd = [
                SMBCmd.NET.value,
                '--use-kerberos', 'required',
                '--use-krb5-ccache', krb5ccache.SYSTEM.value,
                'ads', 'keytab',
                'add_update_ads', service
            ]

            netads = subprocess.run(cmd, check=False, capture_output=True)
            if netads.returncode != 0:
                raise CallError(
                    'Failed to set spn entry: '
                    f'{netads.stdout.decode().strip()}'
                )

        self.call_sync('kerberos.keytab.store_ad_keytab')

    def _health_check_impl(self) -> None:
        self._health_check_ad()
        self._health_check_krb5()
