import datetime
import enum
import errno
import grp
import json
import os
import pwd
import shutil
import socket
import subprocess
import threading
import tdb
import time

from dns import resolver
from middlewared.plugins.smb import SMBCmd, SMBPath, WBCErr
from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import job, private, ConfigService, Service, ValidationError, ValidationErrors
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list, run
from middlewared.plugins.directoryservices import DSStatus
from middlewared.plugins.idmap import DSType
from middlewared.plugins.kerberos import krb5ccache
import middlewared.utils.osc as osc

from samba.dcerpc.messaging import MSG_WINBIND_ONLINE


class neterr(enum.Enum):
    JOINED = 1
    NOTJOINED = 2
    FAULT = 3

    def to_status(errstr):
        errors_to_rejoin = [
            '0xfffffff6',
            'The name provided is not a properly formed account name',
            'The attempted logon is invalid.'
        ]
        for err in errors_to_rejoin:
            if err in errstr:
                return neterr.NOTJOINED

        return neterr.FAULT


class SRV(enum.Enum):
    DOMAINCONTROLLER = '_ldap._tcp.dc._msdcs.'
    FORESTGLOBALCATALOG = '_ldap._tcp.gc._msdcs.'
    GLOBALCATALOG = '_gc._tcp.'
    KERBEROS = '_kerberos._tcp.'
    KERBEROSDOMAINCONTROLLER = '_kerberos._tcp.dc._msdcs.'
    KPASSWD = '_kpasswd._tcp.'
    LDAP = '_ldap._tcp.'
    PDC = '_ldap._tcp.pdc._msdcs.'


class ActiveDirectory_DNS(object):
    def __init__(self, **kwargs):
        super(ActiveDirectory_DNS, self).__init__()
        self.ad = kwargs.get('conf')
        self.logger = kwargs.get('logger')
        return

    def _get_SRV_records(self, host, dns_timeout):
        """
        Set resolver timeout to 1/3 of the lifetime. The timeout defines
        how long to wait before moving on to the next nameserver in resolv.conf
        """
        srv_records = []

        if not host:
            return srv_records

        r = resolver.Resolver()
        r.lifetime = dns_timeout
        r.timeout = r.lifetime / 3

        try:

            answers = r.query(host, 'SRV')
            srv_records = sorted(
                answers,
                key=lambda a: (int(a.priority), int(a.weight))
            )

        except Exception:
            srv_records = []

        return srv_records

    def port_is_listening(self, host, port, timeout=1):
        ret = False

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            s.settimeout(timeout)

        try:
            s.connect((host, port))
            ret = True

        except Exception as e:
            self.logger.debug("connection to %s failed with error: %s",
                              host, e)
            ret = False

        finally:
            s.close()

        return ret

    def _get_servers(self, srv_prefix):
        """
        We will first try fo find servers based on our AD site. If we don't find
        a server in our site, then we populate list for whole domain. Ticket #27584
        Domain Controllers, Forest Global Catalog Servers, and Kerberos Domain Controllers
        need the site information placed before the 'msdcs' component of the host entry.t
        """
        servers = []
        if not self.ad['domainname']:
            return servers

        if self.ad['site'] and self.ad['site'] != 'Default-First-Site-Name':
            if 'msdcs' in srv_prefix.value:
                parts = srv_prefix.value.split('.')
                srv = '.'.join([parts[0], parts[1]])
                msdcs = '.'.join([parts[2], parts[3]])
                host = f"{srv}.{self.ad['site']}._sites.{msdcs}.{self.ad['domainname']}"
            else:
                host = f"{srv_prefix.value}{self.ad['site']}._sites.{self.ad['domainname']}"
        else:
            host = f"{srv_prefix.value}{self.ad['domainname']}"

        servers = self._get_SRV_records(host, self.ad['dns_timeout'])

        if not servers and self.ad['site']:
            host = f"{srv_prefix.value}{self.ad['domainname']}"
            servers = self._get_SRV_records(host, self.ad['dns_timeout'])

        return servers

    def get_n_working_servers(self, srv=SRV['DOMAINCONTROLLER'], number=1):
        """
        :get_n_working_servers: often only a few working servers are needed and not the whole
        list available on the domain. This takes the SRV record type and number of servers to get
        as arguments.
        """
        servers = self._get_servers(srv)
        found_servers = []
        for server in servers:
            if len(found_servers) == number:
                break

            host = server.target.to_text(True)
            port = int(server.port)
            if self.port_is_listening(host, port, timeout=self.ad['timeout']):
                server_info = {'host': host, 'port': port}
                found_servers.append(server_info)

        if self.ad['verbose_logging']:
            self.logger.debug(f'Request for [{number}] of server type [{srv.name}] returned: {found_servers}')
        return found_servers


class ActiveDirectoryModel(sa.Model):
    __tablename__ = 'directoryservice_activedirectory'

    id = sa.Column(sa.Integer(), primary_key=True)
    ad_domainname = sa.Column(sa.String(120))
    ad_bindname = sa.Column(sa.String(120))
    ad_bindpw = sa.Column(sa.EncryptedText())
    ad_verbose_logging = sa.Column(sa.Boolean())
    ad_allow_trusted_doms = sa.Column(sa.Boolean())
    ad_use_default_domain = sa.Column(sa.Boolean())
    ad_allow_dns_updates = sa.Column(sa.Boolean())
    ad_disable_freenas_cache = sa.Column(sa.Boolean())
    ad_restrict_pam = sa.Column(sa.Boolean())
    ad_site = sa.Column(sa.String(120), nullable=True)
    ad_timeout = sa.Column(sa.Integer())
    ad_dns_timeout = sa.Column(sa.Integer())
    ad_nss_info = sa.Column(sa.String(120), nullable=True)
    ad_enable = sa.Column(sa.Boolean())
    ad_kerberos_realm_id = sa.Column(sa.ForeignKey('directoryservice_kerberosrealm.id', ondelete='SET NULL'),
                                     index=True, nullable=True)
    ad_kerberos_principal = sa.Column(sa.String(255))
    ad_createcomputer = sa.Column(sa.String(255))


class ActiveDirectoryService(ConfigService):
    class Config:
        service = "activedirectory"
        datastore = 'directoryservice.activedirectory'
        datastore_extend = "activedirectory.ad_extend"
        datastore_prefix = "ad_"

    @private
    async def ad_extend(self, ad):
        smb = await self.middleware.call('smb.config')
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        if smb_ha_mode == 'STANDALONE':
            ad.update({
                'netbiosname': smb['netbiosname'],
                'netbiosalias': smb['netbiosalias']
            })
        elif smb_ha_mode == 'UNIFIED':
            ngc = await self.middleware.call('network.configuration.config')
            ad.update({
                'netbiosname': ngc['hostname_virtual'],
                'netbiosalias': smb['netbiosalias']
            })
        elif smb_ha_mode == 'LEGACY':
            ngc = await self.middleware.call('network.configuration.config')
            ad.update({
                'netbiosname': ngc['hostname'],
                'netbiosname_b': ngc['hostname_b'],
                'netbiosalias': smb['netbiosalias']
            })

        if ad.get('nss_info'):
            ad['nss_info'] = ad['nss_info'].upper()

        if ad.get('kerberos_realm'):
            ad['kerberos_realm'] = ad['kerberos_realm']['id']

        return ad

    @private
    async def ad_compress(self, ad):
        """
        Convert kerberos realm to id. Force domain to upper-case. Remove
        foreign entries.
        kinit will fail if domain name is lower-case.
        """
        for key in ['netbiosname', 'netbiosalias', 'netbiosname_a', 'netbiosname_b']:
            if key in ad:
                ad.pop(key)

        if ad.get('nss_info'):
            ad['nss_info'] = ad['nss_info'].upper()

        return ad

    @accepts()
    async def nss_info_choices(self):
        """
        Returns list of available LDAP schema choices.
        """
        return await self.middleware.call('directoryservices.nss_info_choices', 'ACTIVEDIRECTORY')

    @private
    async def update_netbios_data(self, old, new):
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        must_update = False
        for key in ['netbiosname', 'netbiosalias', 'netbiosname_a', 'netbiosname_b']:
            if key in new and old[key] != new[key]:
                must_update = True if new[key] else False

        if smb_ha_mode == 'STANDALONE' and must_update:
            await self.middleware.call(
                'smb.update',
                {
                    'netbiosname': new['netbiosname'],
                    'netbiosalias': new['netbiosalias']
                }
            )

        elif smb_ha_mode == 'UNIFIED' and must_update:
            if not await self.middleware.call('smb.validate_netbios_name', new['netbiosname']):
                raise ValidationError('activedirectory_update.netbiosname', "Invalid NetBIOS name")

            await self.middleware.call('smb.update', {'netbiosalias': new['netbiosalias']})
            await self.middleware.call('network.configuration.update', {'hostname_virtual': new['netbiosname']})

        elif smb_ha_mode == 'LEGACY' and must_update:
            await self.middleware.call('smb.update', {'netbiosalias': new['netbiosalias']})
            await self.middleware.call(
                'network.configuration.update',
                {
                    'hostname': new['netbiosname'],
                    'hostname_b': new['netbiosname_b']
                }
            )
        return

    @private
    async def common_validate(self, new, old, verrors):
        if new['kerberos_realm'] and new['kerberos_realm'] != old['kerberos_realm']:
            if not await self.middleware.call('kerberos.realm.query', [("id", "=", new['kerberos_realm'])]):
                verrors.add(
                    'activedirectory_update.kerberos_realm',
                    'Invalid Kerberos realm id. Realm does not exist.'
                )

        if not new["enable"]:
            return

        ldap_enabled = (await self.middleware.call("ldap.config"))['enable']
        if ldap_enabled:
            verrors.add(
                "activedirectory_update.enable",
                "Active Directory service may not be enabled while LDAP service is enabled."
            )
        if new["enable"] and old["enable"] and new["kerberos_realm"] != old["kerberos_realm"]:
            verrors.add(
                "activedirectory_update.kerberos_realm",
                "Kerberos realm may not be be altered while the AD service is enabled. "
                "This is to avoid introducing possible configuration errors that may result "
                "in a production outage."
            )
        if not new["bindpw"] and not new["kerberos_principal"]:
            verrors.add(
                "activedirectory_update.bindname",
                "Bind credentials or kerberos keytab are required to join an AD domain."
            )
        if new["bindpw"] and new["kerberos_principal"]:
            verrors.add(
                "activedirectory_update.kerberos_principal",
                "Simultaneous keytab and password authentication are not permitted."
            )
        if not new["domainname"]:
            verrors.add(
                "activedirectory_update.domainname",
                "AD domain name is required."
            )

    @accepts(Dict(
        'activedirectory_update',
        Str('domainname', required=True),
        Str('bindname'),
        Str('bindpw', private=True),
        Bool('verbose_logging'),
        Bool('use_default_domain'),
        Bool('allow_trusted_doms'),
        Bool('allow_dns_updates'),
        Bool('disable_freenas_cache'),
        Bool('restrict_pam', default=False),
        Str('site', null=True),
        Int('kerberos_realm', null=True),
        Str('kerberos_principal', null=True),
        Int('timeout', default=60),
        Int('dns_timeout', default=10),
        Str('nss_info', null=True, default='', enum=['SFU', 'SFU20', 'RFC2307']),
        Str('createcomputer'),
        Str('netbiosname'),
        Str('netbiosname_b'),
        List('netbiosalias'),
        Bool('enable'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update active directory configuration.
        `domainname` full DNS domain name of the Active Directory domain.

        `bindname` username used to perform the intial domain join.

        `bindpw` password used to perform the initial domain join. User-
        provided credentials are used to obtain a kerberos ticket, which
        is used to perform the actual domain join.

        `verbose_logging` increase logging during the domain join process.

        `use_default_domain` controls whether domain users and groups have
        the pre-windows 2000 domain name prepended to the user account. When
        enabled, the user appears as "administrator" rather than
        "EXAMPLE\administrator"

        `allow_trusted_doms` enable support for trusted domains. If this
        parameter is enabled, then separate idmap backends _must_ be configured
        for each trusted domain, and the idmap cache should be cleared.

        `allow_dns_updates` during the domain join process, automatically
        generate DNS entries in the AD domain for the NAS. If this is disabled,
        then a domain administrator must manually add appropriate DNS entries
        for the NAS. This parameter is recommended for TrueNAS HA servers.

        `disable_freenas_cache` disables active caching of AD users and groups.
        When disabled, only users cached in winbind's internal cache are
        visible in GUI dropdowns. Disabling active caching is recommended
        in environments with a large amount of users.

        `site` AD site of which the NAS is a member. This parameter is auto-
        detected during the domain join process. If no AD site is configured
        for the subnet in which the NAS is configured, then this parameter
        appears as 'Default-First-Site-Name'. Auto-detection is only performed
        during the initial domain join.

        `kerberos_realm` in which the server is located. This parameter is
        automatically populated during the initial domain join. If the NAS has
        an AD site configured and that site has multiple kerberos servers, then
        the kerberos realm is automatically updated with a site-specific
        configuration to use those servers. Auto-detection is only performed
        during initial domain join.

        `kerberos_principal` kerberos principal to use for AD-related
        operations outside of Samba. After intial domain join, this field is
        updated with the kerberos principal associated with the AD machine
        account for the NAS.

        `nss_info` controls how Winbind retrieves Name Service Information to
        construct a user's home directory and login shell. This parameter
        is only effective if the Active Directory Domain Controller supports
        the Microsoft Services for Unix (SFU) LDAP schema.

        `timeout` timeout value for winbind-related operations. This value may
        need to be increased in  environments with high latencies for
        communications with domain controllers or a large number of domain
        controllers. Lowering the value may cause status checks to fail.

        `dns_timeout` timeout value for DNS queries during the initial domain
        join. This value is also set as the NETWORK_TIMEOUT in the ldap config
        file.

        `createcomputer` Active Directory Organizational Unit in which new
        computer accounts are created.

        The OU string is read from top to bottom without RDNs. Slashes ("/")
        are used as delimiters, like `Computers/Servers/NAS`. The backslash
        ("\\") is used to escape characters but not as a separator. Backslashes
        are interpreted at multiple levels and might require doubling or even
        quadrupling to take effect.

        When this field is blank, new computer accounts are created in the
        Active Directory default OU.

        The Active Directory service is started after a configuration
        update if the service was initially disabled, and the updated
        configuration sets `enable` to `True`. The Active Directory
        service is stopped if `enable` is changed to `False`. If the
        configuration is updated, but the initial `enable` state is `True`, and
        remains unchanged, then the samba server is only restarted.

        During the domain join, a kerberos keytab for the newly-created AD
        machine account is generated. It is used for all future
        LDAP / AD interaction and the user-provided credentials are removed.
        """
        verrors = ValidationErrors()
        old = await self.config()
        new = old.copy()
        new.update(data)
        new['domainname'] = new['domainname'].upper()
        try:
            await self.update_netbios_data(old, new)
        except Exception as e:
            raise ValidationError('activedirectory_update.netbiosname', str(e))

        await self.common_validate(new, old, verrors)

        verrors.check()

        if new['enable']:
            if new['allow_trusted_doms'] and not await self.middleware.call('idmap.may_enable_trusted_domains'):
                raise ValidationError(
                    'activedirectory.allow_trusted_doms',
                    'Configuration for trusted domains requires that the idmap backend '
                    'be configured to handle these domains. There are two possible strategies to '
                    'achieve this. The first strategy is to use the AUTORID backend for the domain '
                    'to which TrueNAS is joined. The second strategy is to separately configure idmap '
                    'ranges for every domain that has a trust relationship with the domain to which '
                    'TrueNAS is joined and which has accounts that will be used on the TrueNAS server. '
                    'NOTE: the topic of how to properly map Windows SIDs to Unix IDs is complex and '
                    'may require consultation with administrators of other Unix servers in the '
                    'Active Directory domain to properly coordinate a comprehensive ID mapping strategy.'
                )

        if new['enable'] and not old['enable']:
            """
            Currently run two health checks prior to validating domain.
            1) Attempt to kinit with user-provided credentials. This is used to
               verify that the credentials are correct.
            2) Check for an overly large time offset. System kerberos libraries
               may not report the time offset as an error during kinit, but the large
               time offset will prevent libads from using the ticket for the domain
               join.
            """
            try:
                domain_info = await self.domain_info(new['domainname'])
            except CallError as e:
                raise ValidationError('activedirectory.domainname', e.errmsg)

            if abs(domain_info['Server time offset']) > 180:
                raise ValidationError(
                    'activedirectory.domainname',
                    'Time offset from Active Directory domain exceeds maximum '
                    'permitted value. This may indicate an NTP misconfiguration.'
                )

            try:
                await self.validate_credentials(new, domain_info['KDC server'])
            except CallError as e:
                if new['kerberos_principal']:
                    method = "activedirectory.kerberos_principal"
                else:
                    method = "activedirectory.bindpw"

                try:
                    msg = e.errmsg.split(":")[-1:][0].strip()
                except Exception:
                    raise e

                if msg == 'Cannot read password while getting initial credentials':
                    # non-interactive kinit fails with KRB5_LIBOS_CANTREADPWD if password is expired
                    # rather than prompting for password change
                    if method == 'activedirectory.kerberos_principal':
                        msg = 'Kerberos keytab is no longer valid.'
                    else:
                        msg = f'Active Directory account password for user {new["bindname"]} is expired.'

                elif msg == "Clients credentials have been revoked":
                    # KRB5KDC_ERR_CLIENT_REVOKED means that the account has been locked in AD
                    if method == "activedirectory.bindpw":
                        method = "activedirectory.bindname"

                    msg = 'Active Directory account is locked.'

                elif msg == 'KDC policy rejects request':
                    # KRB5KDC_ERR_POLICY
                    msg = (
                        'Active Directory security policy rejected request to obtain kerberos ticket. '
                        'This may occur if the bind account has been configured to deny interactive '
                        'logons or require two-factor authentication. Depending on organizational '
                        'security policies, one may be required to pre-generate a kerberos keytab '
                        'and upload to TrueNAS server for use during join process.'
                    )
                elif msg.endswith('not found in Kerberos database') or msg.endswith('unknown'):
                    # KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN
                    if method == "activedirectory.bindpw":
                        method = "activedirectory.bindname"

                    msg = (
                        "Client's credentials were not found on remote domain controller. The most "
                        "common reasons for the domain controller to return this response is due to a "
                        "typo in the service account name or the service or the computer account being "
                        "deleted from Active Directory."
                    )

                if not msg:
                    # failed to parse, re-raise original error message
                    raise

                raise ValidationError(
                    method, f'Failed to validate bind credentials: {msg}'
                )
        elif new['enable'] and old['enable']:
            permitted_keys = [
                'verbose_logging',
                'use_default_domain',
                'allow_trusted_domains',
                'disable_freenas_cache',
                'restrict_pam',
                'timeout',
                'dns_timeout'
            ]
            for entry in new.keys():
                if new[entry] != old[entry] and entry not in permitted_keys:
                    raise ValidationError(
                        f'activedirectory.{entry}',
                        'Parameter may not be changed while the Active Directory service is enabled.'
                    )

        new = await self.ad_compress(new)
        await self.middleware.call(
            'datastore.update',
            'directoryservice.activedirectory',
            old['id'],
            new,
            {'prefix': 'ad_'}
        )

        start = False
        stop = False

        if not old['enable']:
            if new['enable']:
                start = True
        else:
            if not new['enable']:
                stop = True

        job = None
        if stop:
            await self.stop()
        if start:
            job = (await self.middleware.call('activedirectory.start')).id

        if not stop and not start and new['enable']:
            await self.middleware.call('service.restart', 'cifs')
        ret = await self.config()
        ret.update({'job_id': job})
        return ret

    @private
    async def set_state(self, state):
        return await self.middleware.call('directoryservices.set_state', {'activedirectory': state.name})

    @accepts()
    async def get_state(self):
        """
        Wrapper function for 'directoryservices.get_state'. Returns only the state of the
        Active Directory service.
        """
        return (await self.middleware.call('directoryservices.get_state'))['activedirectory']

    @private
    async def set_idmap(self, trusted_domains, our_domain):
        idmap = await self.middleware.call('idmap.query',
                                           [('id', '=', DSType.DS_TYPE_ACTIVEDIRECTORY.value)],
                                           {'get': True})
        idmap_id = idmap.pop('id')
        if not idmap['range_low']:
            idmap['range_low'], idmap['range_high'] = await self.middleware.call('idmap.get_next_idmap_range')
        idmap['dns_domain_name'] = our_domain.upper()
        await self.middleware.call('idmap.update', idmap_id, idmap)

    @private
    @job(lock="AD_start")
    async def start(self, job):
        """
        Start AD service. In 'UNIFIED' HA configuration, only start AD service
        on active storage controller.
        """
        ad = await self.config()
        smb = await self.middleware.call('smb.config')
        smb_ha_mode = await self.middleware.call('smb.reset_smb_ha_mode')
        if smb_ha_mode == 'UNIFIED':
            if (failover_status := await self.middleawre.call('failover.status')) != 'MASTER':
                self.logger.error('Skipping Active Directory start because node failover status is: %s', failover_status)
                return

        state = await self.get_state()
        if state in [DSStatus['JOINING'], DSStatus['LEAVING']]:
            raise CallError(f'Active Directory Service has status of [{state}]. Wait until operation completes.', errno.EBUSY)

        dc_info = await self.lookup_dc(ad['domainname'])
        await self.set_state(DSStatus['JOINING'])
        job.set_progress(0, 'Preparing to join Active Directory')
        if ad['verbose_logging']:
            self.logger.debug('Starting Active Directory service for [%s]', ad['domainname'])

        await self.middleware.call('datastore.update', self._config.datastore, ad['id'], {'ad_enable': True})
        await self.middleware.call('etc.generate', 'hostname')

        """
        Kerberos realm field must be populated so that we can perform a kinit
        and use the kerberos ticket to execute 'net ads' commands.
        """
        job.set_progress(5, 'Configuring Kerberos Settings.')
        if not ad['kerberos_realm']:
            realms = await self.middleware.call('kerberos.realm.query', [('realm', '=', ad['domainname'])])

            if realms:
                realm_id = realms[0]['id']
            else:
                realm_id = await self.middleware.call('datastore.insert',
                                                      'directoryservice.kerberosrealm',
                                                      {'krb_realm': ad['domainname'].upper()})

            await self.middleware.call('datastore.update',
                                       self._config.datastore,
                                       ad['id'], {'ad_kerberos_realm': realm_id})
            ad = await self.config()

        if not await self.middleware.call('kerberos._klist_test'):
            await self.middleware.call('kerberos.start')

        """
        'workgroup' is the 'pre-Windows 2000 domain name'. It must be set to the nETBIOSName value in Active Directory.
        This must be properly configured in order for Samba to work correctly as an AD member server.
        'site' is the ad site of which the NAS is a member. If sites and subnets are unconfigured this will
        default to 'Default-First-Site-Name'.
        """

        job.set_progress(20, 'Detecting Active Directory Site.')
        if not ad['site']:
            ad['site'] = dc_info['Client Site Name']
            if dc_info['Client Site Name'] != 'Default-First-Site-Name':
                await self.middleware.call('activedirectory.set_kerberos_servers', ad)

        job.set_progress(30, 'Detecting Active Directory NetBIOS Domain Name.')

        if not smb['workgroup'] or smb['workgroup'] == 'WORKGROUP':
            netbios_domain_name = dc_info['Pre-Win2k Domain']
            await self.middleware.call('datastore.update', 'services.cifs', {'cifs_srv_workgroup': netbios_domain_name})

        await self.middleware.call('etc.generate', 'smb')

        """
        Check response of 'net ads testjoin' to determine whether the server needs to be joined to Active Directory.
        Only perform the domain join if we receive the exact error code indicating that the server is not joined to
        Active Directory. 'testjoin' will fail if the NAS boots before the domain controllers in the environment.
        In this case, samba should be started, but the directory service reported in a FAULTED state.
        """

        job.set_progress(40, 'Performing testjoin to Active Directory Domain')

        machine_acct = await self.middleware.call('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']])
        ret = await self._net_ads_testjoin(smb['workgroup'])
        if ret == neterr.NOTJOINED or not machine_acct:
            job.set_progress(50, 'Joining Active Directory Domain')
            self.logger.debug(f"Test join to {ad['domainname']} failed. Performing domain join.")
            await self._net_ads_join()
            await self._register_virthostname(ad, smb, smb_ha_mode)
            if smb_ha_mode != 'LEGACY':
                """
                Manipulating the SPN entries must be done with elevated privileges. Add NFS service
                principals while we have these on-hand. Once added, force a refresh of the system
                keytab so that the NFS principal will be available for gssd.
                """
                job.set_progress(60, 'Adding NFS Principal entries.')

                try:
                    await self.add_nfs_spn(ad)
                except Exception:
                    self.logger.warning("Failed to add NFS spn to active directory "
                                        "computer object.", exc_info=True)

                job.set_progress(70, 'Storing computer account keytab.')
                kt_id = await self.middleware.call('kerberos.keytab.store_samba_keytab')
                if kt_id:
                    self.logger.debug('Successfully generated keytab for computer account. Clearing bind credentials')
                    await self.middleware.call(
                        'datastore.update',
                        'directoryservice.activedirectory',
                        ad['id'],
                        {'ad_bindpw': '', 'ad_kerberos_principal': f'{ad["netbiosname"].upper()}$@{ad["domainname"]}'}
                    )
                    ad = await self.config()

            ret = neterr.JOINED

            job.set_progress(80, 'Configuring idmap backend and NTP servers.')
            await self.middleware.call('service.update', 'cifs', {'enable': True})
            await self.set_idmap(ad['allow_trusted_doms'], ad['domainname'])
            await self.middleware.call('activedirectory.set_ntp_servers', ad['domainname'])

        job.set_progress(90, 'Restarting SMB server.')
        await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        if ret == neterr.JOINED:
            await self.set_state(DSStatus['HEALTHY'])
            await self.middleware.call('admonitor.start')
            await self.middleware.call('activedirectory.get_cache')
            if ad['verbose_logging']:
                self.logger.debug('Successfully started AD service for [%s].', ad['domainname'])

            if smb_ha_mode == "LEGACY" and (await self.middleware.call('failover.status')) == 'MASTER':
                job.set_progress(95, 'starting active directory on standby controller')
                try:
                    await self.middleware.call('failover.call_remote', 'activedirectory.start')
                except Exception:
                    self.logger.warning('Failed to start active directory service on standby controller', exc_info=True)
        else:
            await self.set_state(DSStatus['FAULTED'])
            self.logger.warning('Server is joined to domain [%s], but is in a faulted state.', ad['domainname'])

        job.set_progress(100, f'Active Directory start completed with status [{ret.name}]')
        return ret.name

    @private
    async def stop(self):
        ad = await self.config()
        await self.middleware.call('datastore.update', self._config.datastore, ad['id'], {'ad_enable': False})
        await self.set_state(DSStatus['LEAVING'])
        await self.middleware.call('admonitor.stop')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('kerberos.stop')
        await self.middleware.call('etc.generate', 'smb')
        await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        await self.set_state(DSStatus['DISABLED'])
        try:
            os.unlink('/var/db/system/.AD_cache_backup')
        except FileNotFoundError:
            pass
        except Exception:
            self.logger.error("Failed to remove AD cache backup. Depending on the circumstances, this may result "
                              "in non-existent usernames and groups appearing in webui dropdown menus.", exc_info=True)
        await self.middleware.call('cache.pop', 'AD_cache')
        flush = await run([SMBCmd.NET.value, "cache", "flush"], check=False)
        if flush.returncode != 0:
            self.logger.warning("Failed to flush samba's general cache after stopping Active Directory service.")

        if (await self.middleware.call('smb.get_smb_ha_mode')) == "LEGACY" and (await self.middleware.call('failover.status')) == 'MASTER':
            try:
                await self.middleware.call('failover.call_remote', 'activedirectory.stop')
            except Exception:
                self.logger.warning('Failed to stop active directory service on standby controller', exc_info=True)

    @private
    async def validate_credentials(self, ad=None, kdc=None):
        """
        Kinit with user-provided credentials is sufficient to determine
        whether the credentials are good. A testbind here is unnecessary.
        """
        if await self.middleware.call('kerberos._klist_test'):
            # Short-circuit credential validation if we have a valid tgt
            return

        if ad is None:
            ad = await self.middleware.call('activedirectory.config')

        data = {'dstype': DSType.DS_TYPE_ACTIVEDIRECTORY.value}
        if kdc:
            data['kinit-options'] = {'kdc_override': {'domain': ad['domainname'], 'kdc': kdc}}

        await self.middleware.call('kerberos.do_kinit', data | ad)

    @private
    def check_clockskew(self, ad=None):
        if not ad:
            ad = self.middleware.call_sync('activedirectory.config')

        domain_info = self.middleware.call_sync('activedirectory.domain_info', ad['domainname'])
        if abs(domain_info['Server time offset']) > 180:
            raise CallError(
                'Time offset from Active Directory domain exceeds maximum '
                'permitted value. This may indicate an NTP misconfiguration.'
            )

        return

    @private
    def validate_domain(self, data=None):
        """
        Methods used to determine AD domain health.
        First we check whether our clock offset has grown to potentially production-impacting
        levels, then we change whether another DC in our AD site is able to take over if the
        DC winbind is currently connected to becomes inaccessible.
        """
        self.check_clockskew(data)
        self.conn_check(data)

    @private
    def machine_account_status(self, domain, dc=None, timeout=15):
        def parse_result(data, out):
            if ':' not in data:
                return

            key, value = data.split(':', 1)
            if key not in out:
                # This is not a line we're interested in
                return

            if type(out[key]) == list:
                out[key].append(value.strip())
            elif out[key] == -1:
                out[key] = int(value.strip())
            else:
                out[key] = value.strip()

            return

        cmd = [
            SMBCmd.NET.value,
            '--realm', domain,
            '--timeout', str(timeout),
            '-P', 'ads', 'status'
        ]
        if dc:
            cmd.extend(['-S', dc])

        results = subprocess.run(cmd, capture_output=True)
        if results.returncode != 0:
            raise CallError(
                'Failed to retrieve machine account status: '
                f'{results.stderr.decode().strip()}'
            )

        output = {
            'userAccountControl': -1,
            'objectSid': None,
            'sAMAccountName': None,
            'dNSHostName': None,
            'servicePrincipalName': [],
            'msDS-SupportedEncryptionTypes': -1
        }

        for line in results.stdout.decode().splitlines():
            parse_result(line, output)

        return output

    @private
    def conn_check(self, data=None, dc=None):
        """
        Temporarily connect to netlogon share of a DC that isn't the one that
        winbind is currently communicating with in order to validate our credentials
        and ability to failover in case of outage on winbind's current DC.

        We only check a single DC because domains can have a significantly large number
        of domain controllers in a given site.
        """
        if data is None:
            data = self.middleware.call_sync("activedirectory.config")

        if dc is None:
            AD_DNS = ActiveDirectory_DNS(conf=data, logger=self.logger)
            res = AD_DNS.get_n_working_servers(SRV['DOMAINCONTROLLER'], 2)
            if len(res) != 2:
                self.logger.warning("Less than two Domain Controllers are in our "
                                    "Active Directory Site. This may result in production "
                                    "outage if the currently connected DC is unreachable.")
                dc = res[0]['host']

            else:
                wb_dcinfo = subprocess.run([SMBCmd.WBINFO.value, "--dc-info", data["domainname"]],
                                           capture_output=True, check=False)
                if wb_dcinfo.returncode == 0:
                    # output "FQDN (ip address)"
                    our_dc = wb_dcinfo.stdout.decode().split()[0]
                    for dc_to_check in res:
                        thehost = dc_to_check['host']
                        if thehost.casefold() != our_dc.casefold():
                            dc = thehost
                else:
                    self.logger.warning("Failed to get DC info from winbindd: %s", wb_dcinfo.stderr.decode())
                    dc = res[0]['host']

        return self.machine_account_status(data['domainname'], dc=dc)

    @accepts()
    async def started(self):
        """
        Issue a no-effect command to our DC. This checks if our secure channel connection to our
        domain controller is still alive. It has much less impact than wbinfo -t.
        Default winbind request timeout is 60 seconds, and can be adjusted by the smb4.conf parameter
        'winbind request timeout ='
        """
        verrors = ValidationErrors()
        config = await self.config()
        if not config['enable']:
            return False

        await self.common_validate(config, config, verrors)

        try:
            verrors.check()
        except Exception:
            await self.middleware.call(
                'datastore.update',
                'directoryservice.activedirectory',
                config['id'],
                {'ad_enable': False}
            )
            raise CallError('Automatically disabling ActiveDirectory service due to invalid configuration.',
                            errno.EINVAL)

        """
        Initialize state to "JOINING" until after booted.
        """
        if not await self.middleware.call('system.ready'):
            await self.set_state(DSStatus['JOINING'])
            return True

        """
        Verify winbindd netlogon connection.
        """
        netlogon_ping = await run([SMBCmd.WBINFO.value, '-P'], check=False)
        if netlogon_ping.returncode != 0:
            wberr = netlogon_ping.stderr.decode().strip('\n')
            err = errno.EFAULT
            for wb in WBCErr:
                if wb.err() in wberr:
                    wberr = wberr.replace(wb.err(), wb.value[0])
                    err = wb.value[1] if wb.value[1] else errno.EFAULT
                    break

            raise CallError(wberr, err)

        try:
            cached_state = await self.middleware.call('cache.get', 'DS_STATE')

            if cached_state['activedirectory'] != 'HEALTHY':
                await self.set_state(DSStatus['HEALTHY'])
        except KeyError:
            await self.set_state(DSStatus['HEALTHY'])

        return True

    @private
    async def _register_virthostname(self, ad, smb, smb_ha_mode):
        """
        This co-routine performs virtual hostname aware
        dynamic DNS updates after joining AD to register
        VIP addresses.
        """
        await self.middleware.call("kerberos.check_ticket")
        if not ad['allow_dns_updates'] or smb_ha_mode == 'STANDALONE':
            return

        vhost = (await self.middleware.call('network.configuration.config'))['hostname_virtual']
        vips = [i['address'] for i in (await self.middleware.call('interface.ip_in_use', {'static': True}))]
        smb_bind_ips = smb['bindip'] if smb['bindip'] else vips
        to_register = set(vips) & set(smb_bind_ips)
        hostname = f'{vhost}.{ad["domainname"]}'
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'dns', 'register', hostname
        ]
        cmd.extend(to_register)
        netdns = await run(cmd, check=False)
        if netdns.returncode != 0:
            self.logger.debug("hostname: %s, ips: %s, text: %s",
                              hostname, to_register, netdns.stderr.decode())

    @private
    async def _parse_join_err(self, msg):
        if len(msg) < 2:
            raise CallError(msg)

        if "Invalid configuration" in msg[1]:
            """
            ./source3/libnet/libnet_join.c will return configuration erros for the
            following situations:
            - incorrect workgroup
            - incorrect realm
            - incorrect security settings
            Unless users set auxiliary parameters, only the first should be a possibility.
            """
            raise CallError(f'{msg[1].rsplit(")",1)[0]}).', errno.EINVAL)
        else:
            raise CallError(msg[1])

    @private
    async def _net_ads_join(self):
        await self.middleware.call("kerberos.check_ticket")
        ad = await self.config()

        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '--realm', ad['domainname'],
            '-d', '5',
            'ads', 'join'
        ]

        if ad['createcomputer']:
            cmd.append(f'createcomputer={ad["createcomputer"]}')

        cmd.append(ad['domainname'])
        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            await self.set_state(DSStatus['FAULTED'])
            await self._parse_join_err(netads.stdout.decode().split(':', 1))

    @private
    async def _net_ads_testjoin(self, workgroup):
        """
        If neterr.NOTJOINED is returned then we will proceed with joining (or re-joining)
        the AD domain. There are currently two reasons to do this:
        1) we're not joined to AD
        2) our computer account was deleted out from under us
        It's generally better to report an error condition to the end user and let them
        fix it, but situation (2) above is straightforward enough to automatically re-join.
        In this case, the error message presents oddly because stale credentials are stored in
        the secrets.tdb file and the message is passed up from underlying KRB5 library.
        """
        await self.middleware.call("kerberos.check_ticket")
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-w', workgroup,
            '-d', '5',
            'ads', 'testjoin'
        ]

        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            errout = netads.stderr.decode()
            with open(f"{SMBPath.LOGDIR.platform()}/domain_testjoin_{int(datetime.datetime.now().timestamp())}.log", "w") as f:
                f.write(errout)

            return neterr.to_status(errout)

        return neterr.JOINED

    @private
    async def net_keytab_add_update_ads(self, service_class):
        """
        Only automatically add NFS SPN entries on domain join
        if kerberized nfsv4 is enabled.
        """
        await self.middleware.call("kerberos.check_ticket")
        if not (await self.middleware.call('nfs.config'))['v4_krb']:
            return False

        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'keytab',
            'add_update_ads', service_class
        ]

        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            raise CallError('failed to set spn entry '
                            f'[{service_class}]: {netads.stdout.decode().strip()}')

        return True

    @accepts()
    async def get_spn_list(self):
        """
        Return list of kerberos SPN entries registered for the server's Active
        Directory computer account. This may not reflect the state of the
        server's current kerberos keytab.
        """
        await self.middleware.call("kerberos.check_ticket")
        spnlist = []
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'setspn', 'list'
        ]
        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            raise CallError(
                f"Failed to generate SPN list: [{netads.stderr.decode().strip()}]"
            )

        for spn in netads.stdout.decode().splitlines():
            if len(spn.split('/')) != 2:
                continue
            spnlist.append(spn.strip())

        return spnlist

    @accepts()
    async def change_trust_account_pw(self):
        """
        Force an update of the AD machine account password. This can be used to
        refresh the Kerberos principals in the server's system keytab.
        """
        await self.middleware.call("kerberos.check_ticket")
        workgroup = (await self.middleware.call('smb.config'))['workgroup']
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-w', workgroup,
            'ads', 'changetrustpw',
        ]
        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            raise CallError(
                f"Failed to update trust password: [{netads.stderr.decode().strip()}] "
                f"stdout: [{netads.stdout.decode().strip()}] "
            )

    @private
    async def add_nfs_spn(self, ad=None):
        if ad is None:
            ad = await self.config()

        ok = await self.net_keytab_add_update_ads('nfs')
        if not ok:
            return False

        return True

    @private
    def get_kerberos_servers(self, ad=None):
        """
        This returns at most 3 kerberos servers located in our AD site. This is to optimize
        kerberos configuration for locations where kerberos servers may span the globe and
        have equal DNS weighting. Since a single kerberos server may represent an unacceptable
        single point of failure, fall back to relying on normal DNS queries in this case.
        """
        if ad is None:
            ad = self.middleware.call_sync('activedirectory.config')
        AD_DNS = ActiveDirectory_DNS(conf=ad, logger=self.logger)
        krb_kdc = AD_DNS.get_n_working_servers(SRV['KERBEROSDOMAINCONTROLLER'], 3)
        krb_admin_server = AD_DNS.get_n_working_servers(SRV['KERBEROS'], 3)
        krb_kpasswd_server = AD_DNS.get_n_working_servers(SRV['KPASSWD'], 3)
        kdc = [i['host'] for i in krb_kdc]
        admin_server = [i['host'] for i in krb_admin_server]
        kpasswd = [i['host'] for i in krb_kpasswd_server]
        for servers in [kdc, admin_server, kpasswd]:
            if len(servers) == 1:
                return None

        return {
            'krb_kdc': ' '.join(kdc),
            'krb_admin_server': ' '.join(admin_server),
            'krb_kpasswd_server': ' '.join(kpasswd)
        }

    @private
    def set_kerberos_servers(self, ad=None):
        if not ad:
            ad = self.middleware.call_sync('activedirectory.config')
        site_indexed_kerberos_servers = self.get_kerberos_servers(ad)
        if site_indexed_kerberos_servers:
            self.middleware.call_sync(
                'datastore.update',
                'directoryservice.kerberosrealm',
                ad['kerberos_realm'],
                site_indexed_kerberos_servers
            )
            self.middleware.call_sync('etc.generate', 'kerberos')

    @private
    async def cache_flush_retry(self, cmd, recursion_cnt=0):
        rv = await run(cmd, check=False)
        if rv.returncode != 0 and not recursion_cnt:
            gencache_flush = await run(['net', 'cache', 'flush'], check=False)
            if gencache_flush.returncode != 0:
                raise CallError(f'Attempt to flush gencache failed with error: {gencache_flush.stderr.decode().strip()}')
            return await self.cache_flush_retry(cmd, recursion_cnt + 1)

        return rv

    @accepts(Str('domain', default=''))
    async def domain_info(self, domain):
        """
        Returns the following information about the currently joined domain:

        `LDAP server` IP address of current LDAP server to which TrueNAS is connected.

        `LDAP server name` DNS name of LDAP server to which TrueNAS is connected

        `Realm` Kerberos realm

        `LDAP port`

        `Server time` timestamp.

        `KDC server` Kerberos KDC to which TrueNAS is connected

        `Server time offset` current time offset from DC.

        `Last machine account password change`. timestamp
        """
        if domain:
            cmd = [SMBCmd.NET.value, '-S', domain, '--json', '--option', f'realm={domain}', 'ads', 'info']
        else:
            cmd = [SMBCmd.NET.value, '--json', 'ads', 'info']

        netads = await self.cache_flush_retry(cmd)
        if netads.returncode != 0:
            err_msg = netads.stderr.decode().strip()
            if err_msg == "Didn't find the ldap server!":
                raise CallError(
                    'Failed to discover Active Directory Domain Controller '
                    'for domain. This may indicate a DNS misconfiguration.',
                    errno.ENOENT
                )

            raise CallError(netads.stderr.decode())

        return json.loads(netads.stdout.decode())

    @private
    async def set_ntp_servers(self, domain):
        """
        Appropriate time sources are a requirement for an AD environment. By default kerberos authentication
        fails if there is more than a 5 minute time difference between the AD domain and the member server.
        """
        ntp_servers = await self.middleware.call('system.ntpserver.query')
        if len(ntp_servers) != 3 or filter_list(ntp_servers, [['freebsd.pool.ntp.org', 'in', 'address']], {'count': True}) != 3:
            return

        try:
            dc_info = await self.lookup_dc(domain)
        except CallError:
            self.logger.warning("Failed to automatically set time source.", exc_info=True)
            return

        if not dc_info['Flags']['Is running time services']:
            return

        dc_name = dc_info["Information for Domain Controller"]

        try:
            await self.middleware.call('system.ntpserver.create', {'address': dc_name, 'prefer': True})
        except Exception:
            self.logger.warning('Failed to configure NTP for the Active Directory domain. Additional '
                                'manual configuration may be required to ensure consistent time offset, '
                                'which is required for a stable domain join.', exc_info=True)
        return

    @private
    async def lookup_dc(self, domain=None, recursion_cnt=0):
        if domain is None:
            domain = (await self.config())['domainname']

        lookup = await self.cache_flush_retry([SMBCmd.NET.value, '--json', '--realm', domain, '-S', domain, 'ads', 'lookup'])
        if lookup.returncode != 0:
            raise CallError("Failed to look up Domain Controller information: "
                            f"{lookup.stderr.decode().strip()}")

        out = json.loads(lookup.stdout.decode())
        return out

    @accepts(
        Dict(
            'leave_ad',
            Str('username', required=True),
            Str('password', required=True, private=True)
        )
    )
    async def leave(self, data):
        """
        Leave Active Directory domain. This will remove computer
        object from AD and clear relevant configuration data from
        the NAS.
        This requires credentials for appropriately-privileged user.
        Credentials are used to obtain a kerberos ticket, which is
        used to perform the actual removal from the domain.
        """
        ad = await self.config()
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')

        ad['dstype'] = DSType.DS_TYPE_ACTIVEDIRECTORY.value
        ad['bindname'] = data.get("username", "")
        ad['bindpw'] = data.get("password", "")
        ad['kerberos_principal'] = ''

        await self.middleware.call('kerberos.do_kinit', ad)

        netads = await run([SMBCmd.NET.value, '-U', data['username'], '-k', 'ads', 'leave'], check=False)
        if netads.returncode != 0:
            self.logger.warning("Failed to leave domain: %s", netads.stderr.decode())

        if smb_ha_mode != 'LEGACY':
            krb_princ = await self.middleware.call(
                'kerberos.keytab.query',
                [('name', '=', 'AD_MACHINE_ACCOUNT')]
            )
            if krb_princ:
                await self.middleware.call('kerberos.keytab.delete', krb_princ[0]['id'])

        await self.middleware.call('datastore.delete', 'directoryservice.kerberosrealm', ad['kerberos_realm'])

        if netads.returncode == 0:
            try:
                pdir = await self.middleware.call("smb.getparm", "private directory", "GLOBAL")
                ts = time.time()
                os.rename(f"{pdir}/secrets.tdb", f"{pdir}/secrets.tdb.bak.{int(ts)}")
                await self.middleware.call("directoryservices.backup_secrets")
            except Exception:
                self.logger.debug("Failed to remove stale secrets file.", exc_info=True)

        await self.middleware.call('activedirectory.update', {'enable': False, 'site': None})
        if smb_ha_mode == 'LEGACY' and (await self.middleware.call('failover.status')) == 'MASTER':
            try:
                await self.middleware.call('failover.call_remote', 'activedirectory.leave', [data])
            except Exception:
                self.logger.warning("Failed to leave AD domain on passive storage controller.", exc_info=True)

        flush = await run([SMBCmd.NET.value, "cache", "flush"], check=False)
        if flush.returncode != 0:
            self.logger.warning("Failed to flush samba's general cache after leaving Active Directory.")

        self.logger.debug("Successfully left domain: %s", ad['domainname'])

    @private
    @job(lock='fill_ad_cache')
    def fill_cache(self, job, force=False):
        """
        Use UID2SID and GID2SID entries in Samba's gencache.tdb to populate the AD_cache.
        Since this can include IDs outside of our configured idmap domains (Local accounts
        will also appear here), there is a check to see if the ID is inside the idmap ranges
        configured for domains that are known to us. Some samba idmap backends support
        id_type_both, in which case the will be GID2SID entries for AD users. getent group
        succeeds in this case (even though the group doesn't exist in AD). Since these
        we don't want to populate the UI cache with these entries, try to getpwnam for
        GID2SID entries. If it's an actual group, getpwnam will fail. This heuristic
        may be revised in the future, but we want to keep things as simple as possible
        here since the list of entries numbers perhaps in the tens of thousands.
        """
        if self.middleware.call_sync('cache.has_key', 'AD_cache') and not force:
            raise CallError('AD cache already exists. Refusing to generate cache.')

        self.middleware.call_sync('cache.pop', 'AD_cache')
        ad = self.middleware.call_sync('activedirectory.config')
        smb = self.middleware.call_sync('smb.config')
        id_type_both_backends = [
            'RID',
            'AUTORID'
        ]
        if not ad['disable_freenas_cache']:
            """
            These calls populate the winbindd cache
            """
            pwd.getpwall()
            grp.getgrall()
        elif ad['bindname']:
            id = subprocess.run(['/usr/bin/id', f"{smb['workgroup']}\\{ad['bindname']}"], capture_output=True)
            if id.returncode != 0:
                self.logger.debug('failed to id AD bind account [%s]: %s', ad['bindname'], id.stderr.decode())

        shutil.copyfile(f'{SMBPath.LOCKDIR.platform()}/gencache.tdb', '/tmp/gencache.tdb')

        gencache = tdb.Tdb('/tmp/gencache.tdb', 0, tdb.DEFAULT, os.O_RDONLY)
        gencache_keys = [x for x in gencache.keys()]
        gencache.close()

        known_domains = []
        local_users = {}
        local_groups = {}
        local_users.update({x['uid']: x for x in self.middleware.call_sync('user.query')})
        local_users.update({x['gid']: x for x in self.middleware.call_sync('group.query')})
        cache_data = {'users': {}, 'groups': {}}
        configured_domains = self.middleware.call_sync('idmap.query')
        user_next_index = group_next_index = 300000000
        for d in configured_domains:
            if d['name'] == 'DS_TYPE_ACTIVEDIRECTORY':
                known_domains.append({
                    'domain': smb['workgroup'],
                    'low_id': d['range_low'],
                    'high_id': d['range_high'],
                    'id_type_both': True if d['idmap_backend'] in id_type_both_backends else False,
                })
            elif d['name'] not in ['DS_TYPE_DEFAULT_DOMAIN', 'DS_TYPE_LDAP']:
                known_domains.append({
                    'domain': d['name'],
                    'low_id': d['range_low'],
                    'high_id': d['range_high'],
                    'id_type_both': True if d['idmap_backend'] in id_type_both_backends else False,
                })

        for key in gencache_keys:
            prefix = key[0:13]
            if prefix != b'IDMAP/UID2SID' and prefix != b'IDMAP/GID2SID':
                continue

            line = key.decode()
            if line.startswith('IDMAP/UID2SID'):
                # tdb keys are terminated with \x00, this must be sliced off before converting to int
                cached_uid = int(line[14:-1])
                """
                Do not cache local users. This is to avoid problems where a local user
                may enter into the id range allotted to AD users.
                """
                if local_users.get(cached_uid, None):
                    continue

                for d in known_domains:
                    if cached_uid in range(d['low_id'], d['high_id']):
                        """
                        Samba will generate UID and GID cache entries when idmap backend
                        supports id_type_both.
                        """
                        try:
                            user_data = pwd.getpwuid(cached_uid)
                            cache_data['users'].update({user_data.pw_name: {
                                'id': user_next_index,
                                'uid': user_data.pw_uid,
                                'username': user_data.pw_name,
                                'unixhash': None,
                                'smbhash': None,
                                'group': {},
                                'home': '',
                                'shell': '',
                                'full_name': user_data.pw_gecos,
                                'builtin': False,
                                'email': '',
                                'password_disabled': False,
                                'locked': False,
                                'sudo': False,
                                'sudo_nopasswd': False,
                                'sudo_commands': [],
                                'microsoft_account': False,
                                'attributes': {},
                                'groups': [],
                                'sshpubkey': None,
                                'local': False,
                                'id_type_both': d['id_type_both']
                            }})
                            user_next_index += 1
                            break
                        except KeyError:
                            break

            if line.startswith('IDMAP/GID2SID'):
                # tdb keys are terminated with \x00, this must be sliced off before converting to int
                cached_gid = int(line[14:-1])
                if local_groups.get(cached_gid, None):
                    continue

                for d in known_domains:
                    if cached_gid in range(d['low_id'], d['high_id']):
                        """
                        Samba will generate UID and GID cache entries when idmap backend
                        supports id_type_both. Actual groups will return key error on
                        attempt to generate passwd struct. It is also possible that the
                        winbindd cache will have stale or expired entries. Failure on getgrgid
                        should not be fatal here.
                        """
                        try:
                            group_data = grp.getgrgid(cached_gid)
                        except KeyError:
                            break

                        cache_data['groups'].update({group_data.gr_name: {
                            'id': group_next_index,
                            'gid': group_data.gr_gid,
                            'group': group_data.gr_name,
                            'builtin': False,
                            'sudo': False,
                            'sudo_nopasswd': False,
                            'sudo_commands': [],
                            'users': [],
                            'local': False,
                            'id_type_both': d['id_type_both']
                        }})
                        group_next_index += 1
                        break

        if not cache_data.get('users'):
            return
        sorted_cache = {}
        sorted_cache['users'] = dict(sorted(cache_data['users'].items()))
        sorted_cache['groups'] = dict(sorted(cache_data['groups'].items()))

        self.middleware.call_sync('cache.put', 'AD_cache', sorted_cache)
        self.middleware.call_sync('dscache.backup')

    @private
    async def get_cache(self):
        """
        Returns cached AD user and group information. If proactive caching is enabled
        then this will contain all AD users and groups, otherwise it contains the
        users and groups that were present in the winbindd cache when the cache was
        last filled. The cache expires and is refilled every 24 hours, or can be
        manually refreshed by calling fill_cache(True).
        """
        if not await self.middleware.call('cache.has_key', 'AD_cache'):
            await self.middleware.call('activedirectory.fill_cache')
            self.logger.debug('cache fill is in progress.')
            return {'users': {}, 'groups': {}}
        return await self.middleware.call('cache.get', 'AD_cache')


class WBStatusThread(threading.Thread):
    def __init__(self, **kwargs):
        super(WBStatusThread, self).__init__()
        self.setDaemon(True)
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.finished = threading.Event()
        self.state = MSG_WINBIND_ONLINE

    def parse_msg(self, data):
        if data == str(DSStatus.LEAVING.value):
            return

        try:
            m = json.loads(data)
        except json.decoder.JSONDecodeError:
            self.logger.debug("Unable to decode winbind status message: "
                              "%s", data)
            return

        new_state = self.state

        if not self.middleware.call_sync('activedirectory.config')['enable']:
            self.logger.debug('Ignoring winbind message for disabled AD service: [%s]', m)
            return

        try:
            new_state = DSStatus(m['winbind_message']).value
        except Exception as e:
            self.logger.debug('Received invalid winbind status message [%s]: %s', m, e)
            return

        if m['domain_name_netbios'] != self.middleware.call_sync('smb.config')['workgroup']:
            self.logger.debug(
                'Domain [%s] changed state to %s',
                m['domain_name_netbios'],
                DSStatus(m['winbind_message']).name
            )
            return

        if self.state != new_state:
            self.logger.debug(
                'State of domain [%s] transistioned to [%s]',
                m['forest_name'], DSStatus(m['winbind_message'])
            )
            self.middleware.call_sync('activedirectory.set_state', DSStatus(m['winbind_message']))
            if new_state == DSStatus.FAULTED.value:
                self.middleware.call_sync(
                    "alert.oneshot_create",
                    "ActiveDirectoryDomainOffline",
                    {"domain": m["domain_name_netbios"]}
                )
            else:
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "ActiveDirectoryDomainOffline",
                    {"domain": m["domain_name_netbios"]}
                )

        self.state = new_state

    def read_messages(self):
        while not self.finished.is_set():
            with open(f'{SMBPath.RUNDIR.platform()}/.wb_fifo') as f:
                data = f.read()
                for msg in data.splitlines():
                    self.parse_msg(msg)

        self.logger.debug('exiting winbind messaging thread')

    def run(self):
        osc.set_thread_name('ad_monitor_thread')
        try:
            self.read_messages()
        except Exception as e:
            self.logger.debug('Failed to run monitor thread %s', e, exc_info=True)

    def setup(self):
        if not os.path.exists(f'{SMBPath.RUNDIR.platform()}/.wb_fifo'):
            os.mkfifo(f'{SMBPath.RUNDIR.platform()}/.wb_fifo')

    def cancel(self):
        """
        Write to named pipe to unblock open() in thread and exit cleanly.
        """
        self.finished.set()
        with open(f'{SMBPath.RUNDIR.platform()}/.wb_fifo', 'w') as f:
            f.write(str(DSStatus.LEAVING.value))


class ADMonitorService(Service):
    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(ADMonitorService, self).__init__(*args, **kwargs)
        self.thread = None
        self.initialized = False
        self.lock = threading.Lock()

    def start(self):
        if not self.middleware.call_sync('activedirectory.config')['enable']:
            self.logger.trace('Active directory is disabled. Exiting AD monitoring.')
            return

        with self.lock:
            if self.initialized:
                return

            thread = WBStatusThread(
                middleware=self.middleware,
            )
            thread.setup()
            self.thread = thread
            thread.start()
            self.initialized = True

    def stop(self):
        thread = self.thread
        if thread is None:
            return

        thread.cancel()
        self.thread = None

        with self.lock:
            self.initialized = False

    def restart(self):
        self.stop()
        self.start()


async def setup(middleware):
    """
    During initial boot let smb_configure script start monitoring once samba's
    rundir is created.
    """
    if await middleware.call('system.ready'):
        await middleware.call('admonitor.start')
