import datetime
import enum
import errno
import json
import os
import time
import contextlib

from middlewared.plugins.smb import SMBCmd, SMBPath
from middlewared.plugins.kerberos import krb5ccache
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, LDAP_DN, List, Ref, returns, Str
from middlewared.service import job, private, TDBWrapConfigService, ValidationError, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.plugins.directoryservices import DSStatus
from middlewared.plugins.idmap import DSType

AD_SMBCONF_PARAMS = {
    "server role": "member server",
    "kerberos method": "secrets and keytab",
    "security": "ADS",
    "local master": False,
    "domain master": False,
    "preferred master": False,
    "winbind cache time": 7200,
    "winbind max domain connections": 10,
    "client ldap sasl wrapping": "seal",
    "template shell": "/bin/sh",
    "template homedir": None,
    "ads dns update": None,
    "realm": None,
    "allow trusted domains": None,
    "winbind enum users": None,
    "winbind enum groups": None,
    "winbind use default domain": None,
    "winbind nss info": None,
}


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


class ActiveDirectoryService(TDBWrapConfigService):
    tdb_defaults = {
        "id": 1,
        "domainname": "",
        "bindname": "",
        "bindpw": "",
        "verbose_logging": False,
        "allow_trusted_doms": False,
        "use_default_domain": False,
        "allow_dns_updates": True,
        "kerberos_principal": "",
        "kerberos_realm": None,
        "createcomputer": "",
        "site": "",
        "timeout": 60,
        "dns_timeout": 10,
        "nss_info": None,
        "disable_freenas_cache": False,
        "restrict_pam": False,
        "enable": False,
    }

    class Config:
        service = "activedirectory"
        datastore = 'directoryservice.activedirectory'
        datastore_extend = "activedirectory.ad_extend"
        datastore_prefix = "ad_"
        cli_namespace = "directory_service.activedirectory"

    @private
    async def convert_schema_to_registry(self, data_in, data_out):
        """
        Convert middleware schema SMB shares to an SMB service definition
        """
        params = AD_SMBCONF_PARAMS.copy()

        if not data_in['enable']:
            return

        for k, v in params.items():
            if v is None:
                continue

            data_out[k] = {"raw": str(v), "parsed": v}

        data_out.update({
            "ads dns update": {"parsed": data_in["allow_dns_updates"]},
            "realm": {"parsed": data_in["domainname"].upper()},
            "allow trusted domains": {"parsed": data_in["allow_trusted_doms"]},
            "winbind enum users": {"parsed": not data_in["disable_freenas_cache"]},
            "winbind enum groups": {"parsed": not data_in["disable_freenas_cache"]},
            "winbind use default domain": {"parsed": data_in["use_default_domain"]},
        })

        if data_in.get("nss_info"):
            data_out["winbind nss info"] = {"parsed": data_in["nss_info"]}

        try:
            home_share = await self.middleware.call('sharing.smb.reg_showshare', 'homes')
            home_path = home_share['parameters']['path']['raw']
        except MatchNotFound:
            home_path = '/var/empty'

        data_out['template homedir'] = {"parsed": f'{home_path}'}

        return

    @private
    async def ad_extend(self, ad):
        smb = await self.middleware.call('smb.config')
        smb_ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        if smb_ha_mode in ['STANDALONE', 'CLUSTERED']:
            ad.update({
                'netbiosname': smb['netbiosname_local'],
                'netbiosalias': smb['netbiosalias']
            })
        elif smb_ha_mode == 'UNIFIED':
            ngc = await self.middleware.call('network.configuration.config')
            ad.update({
                'netbiosname': ngc['hostname_virtual'],
                'netbiosalias': smb['netbiosalias']
            })

        if ad.get('nss_info'):
            ad['nss_info'] = ad['nss_info'].upper()

        if ad.get('kerberos_realm') and type(ad['kerberos_realm']) == dict:
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
    @returns(Ref('nss_info_ad'))
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
                if old['enable']:
                    raise ValidationError(
                        f'activedirectory.{key}',
                        'NetBIOS names may not be changed while service is enabled.'
                    )

                must_update = True
                break

        if not must_update:
            return

        if smb_ha_mode != 'UNIFIED':
            await self.middleware.call(
                'smb.update',
                {
                    'netbiosname': new['netbiosname'],
                    'netbiosalias': new['netbiosalias']
                }
            )

        # updating hostname virtual does not go through same valiation as netbios name
        # in smb.update and so perform additional validation here
        elif not await self.middleware.call('smb.validate_netbios_name', new['netbiosname']):
            raise ValidationError('activedirectory_update.netbiosname', 'Invalid NetBIOS name')

        else:
            await self.middleware.call('smb.update', {'netbiosalias': new['netbiosalias']})
            await self.middleware.call('network.configuration.update', {'hostname_virtual': new['netbiosname']})

        return

    @private
    async def common_validate(self, new, old, verrors):
        if new['kerberos_realm'] and new['kerberos_realm'] != old['kerberos_realm']:
            realm = await self.middleware.call('kerberos.realm.query', [("id", "=", new['kerberos_realm'])])
            if not realm:
                verrors.add(
                    'activedirectory_update.kerberos_realm',
                    'Invalid Kerberos realm id. Realm does not exist.'
                )

        if not new["enable"]:
            return

        ldap_enabled = (await self.middleware.call('ldap.config'))['enable']
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
        await self.middleware.call("smb.cluster_check")
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
            if await self.middleware.call('failover.licensed'):
                if await self.middleware.call('systemdataset.is_boot_pool'):
                    raise ValidationError(
                        'activedirectory.enable',
                        'Active Directory may not be enabled while '
                        'system dataset is on the boot pool'
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
                await self.validate_credentials(new)
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

                elif msg == "Client's credentials have been revoked while getting initial credentials":
                    # KRB5KDC_ERR_CLIENT_REVOKED means that the account has been locked in AD
                    msg = 'Active Directory account is locked.'

                elif msg == 'KDC policy rejects request while getting initial credentials':
                    # KRB5KDC_ERR_POLICY
                    msg = (
                        'Active Directory security policy rejected request to obtain kerberos ticket. '
                        'This may occur if the bind account has been configured to deny interactive '
                        'logons or require two-factor authentication. Depending on organizational '
                        'security policies, one may be required to pre-generate a kerberos keytab '
                        'and upload to TrueNAS server for use during join process.'
                    )

                if not msg:
                    # failed to parse, re-raise original error message
                    raise

                raise ValidationError(
                    method, f'Failed to validate bind credentials: {msg}'
                )

        new = await self.ad_compress(new)
        ret = await super().do_update(new)

        diff = await self.diff_conf_and_registry(new)
        await self.middleware.call('sharing.smb.apply_conf_diff', 'GLOBAL', diff)

        job = None
        if not old['enable'] and new['enable']:
            ngc = await self.middleware.call('network.configuration.config')
            if not ngc['domain'] or ngc['domain'] == 'local':
                try:
                    await self.middleware.call(
                        'network.configuration.update',
                        {'domain': ret['domainname']}
                    )
                except CallError:
                    self.logger.warning(
                        'Failed to update domain name in network configuration '
                        'to match active directory value of %s', ret['domainname'], exc_info=True
                    )

            job = (await self.middleware.call('activedirectory.start')).id

        elif not new['enable'] and old['enable']:
            job = (await self.middleware.call('activedirectory.stop')).id

        elif new['enable'] and old['enable']:
            await self.middleware.call('service.restart', 'idmap')

        ret.update({'job_id': job})
        return ret

    @private
    async def diff_conf_and_registry(self, data):
        to_check = {}
        smbconf = (await self.middleware.call('smb.reg_globals'))['ds']
        await self.convert_schema_to_registry(data, to_check)

        r = smbconf
        s_keys = set(to_check.keys())
        r_keys = set(r.keys())
        intersect = s_keys.intersection(r_keys)
        return {
            'added': {x: to_check[x] for x in s_keys - r_keys},
            'removed': {x: r[x] for x in r_keys - s_keys},
            'modified': {x: to_check[x] for x in intersect if to_check[x] != r[x]},
        }

    @private
    async def synchronize(self, data=None):
        if data is None:
            data = await self.config()

        diff = await self.diff_conf_and_registry(data)
        await self.middleware.call('sharing.smb.apply_conf_diff', 'GLOBAL', diff)

    @private
    async def set_state(self, state):
        return await self.middleware.call('directoryservices.set_state', {'activedirectory': state})

    @accepts()
    @returns(Str('directoryservice_state', enum=[x.name for x in DSStatus], register=True))
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
        if trusted_domains:
            await self.middleware.call('idmap.autodiscover_trusted_domains')

    @private
    @job(lock="AD_start_stop")
    async def start(self, job):
        """
        Start AD service. In 'UNIFIED' HA configuration, only start AD service
        on active storage controller.
        """
        await self.middleware.call("smb.cluster_check")
        ad = await self.config()
        smb = await self.middleware.call('smb.config')
        workgroup = smb['workgroup']
        smb_ha_mode = await self.middleware.call('smb.reset_smb_ha_mode')
        if smb_ha_mode == 'UNIFIED':
            if await self.middleware.call('failover.status') != 'MASTER':
                return

        state = await self.get_state()
        if state in [DSStatus['JOINING'], DSStatus['LEAVING']]:
            raise CallError(f'Active Directory Service has status of [{state}]. Wait until operation completes.', errno.EBUSY)

        dc_info = await self.lookup_dc(ad['domainname'])

        await self.set_state(DSStatus['JOINING'].name)
        job.set_progress(0, 'Preparing to join Active Directory')
        if ad['verbose_logging']:
            self.logger.debug('Starting Active Directory service for [%s]', ad['domainname'])

        await super().do_update({'enable': True})
        await self.synchronize()
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
                realm_id = await self.middleware.call(
                    'kerberos.realm.direct_create',
                    {'realm': ad['domainname'].upper(), 'kdc': '', 'admin_server': '', 'kpasswd_server': ''}
                )

            await self.direct_update({"kerberos_realm": realm_id})
            ad = await self.config()

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
        if workgroup != dc_info['Pre-Win2k Domain']:
            self.logger.debug('Updating SMB workgroup to %s', dc_info['Pre-Win2k Domain'])
            await self.middleware.call('smb.direct_update', {'workgroup': dc_info['Pre-Win2k Domain']})

        await self.middleware.call('smb.initialize_globals')

        """
        Check response of 'net ads testjoin' to determine whether the server needs to be joined to Active Directory.
        Only perform the domain join if we receive the exact error code indicating that the server is not joined to
        Active Directory. 'testjoin' will fail if the NAS boots before the domain controllers in the environment.
        In this case, samba should be started, but the directory service reported in a FAULTED state.
        """

        job.set_progress(40, 'Performing testjoin to Active Directory Domain')
        ret = await self._net_ads_testjoin(workgroup, ad)
        if ret == neterr.NOTJOINED:
            job.set_progress(50, 'Joining Active Directory Domain')
            self.logger.debug(f"Test join to {ad['domainname']} failed. Performing domain join.")
            await self._net_ads_join(ad)
            await self.middleware.call('activedirectory.register_dns', ad, smb, smb_ha_mode)
            """
            Manipulating the SPN entries must be done with elevated privileges. Add NFS service
            principals while we have these on-hand.
            Since this may potentially take more than a minute to complete, run in background job.
            """
            job.set_progress(60, 'Adding NFS Principal entries.')
            # Skip health check for add_nfs_spn since by this point our AD join should be de-facto healthy.
            spn_job = await self.middleware.call('activedirectory.add_nfs_spn', ad['netbiosname'], ad['domainname'], False, False)
            await spn_job.wait()

            job.set_progress(70, 'Storing computer account keytab.')
            kt_id = await self.middleware.call('kerberos.keytab.store_samba_keytab')
            if kt_id:
                self.logger.debug('Successfully generated keytab for computer account. Clearing bind credentials')
                ad = await self.direct_update({
                    'bindpw': '',
                    'kerberos_principal': f'{ad["netbiosname"].upper()}$@{ad["domainname"]}'
                })

            ret = neterr.JOINED

            job.set_progress(80, 'Configuring idmap backend and NTP servers.')
            await self.middleware.call('service.update', 'cifs', {'enable': True})
            await self.set_idmap(ad['allow_trusted_doms'], ad['domainname'])
            await self.middleware.call('activedirectory.set_ntp_servers')

        job.set_progress(90, 'Restarting SMB server.')
        await self.middleware.call('idmap.synchronize')
        await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('etc.generate', 'pam')
        if ret == neterr.JOINED:
            await self.set_state(DSStatus['HEALTHY'].name)
            await self.middleware.call('admonitor.start')
            await self.middleware.call('service.start', 'dscache')
            if ad['verbose_logging']:
                self.logger.debug('Successfully started AD service for [%s].', ad['domainname'])

        else:
            await self.set_state(DSStatus['FAULTED'].name)
            self.logger.warning('Server is joined to domain [%s], but is in a faulted state.', ad['domainname'])

        if smb_ha_mode == 'CLUSTERED':
            job.set_progress(95, 'Propagating activedirectory service reload to cluster members')
            cl_reload = await self.middleware.call('clusterjob.submit', 'activedirectory.cluster_reload', 'START')
            await cl_reload.wait()

        job.set_progress(100, f'Active Directory start completed with status [{ret.name}]')
        return ret.name

    @private
    @job(lock="AD_start_stop")
    async def stop(self, job):
        job.set_progress(0, 'Preparing to stop Active Directory service')
        await self.middleware.call("smb.cluster_check")
        await self.direct_update({"enable": False})

        await self.set_state(DSStatus['LEAVING'].name)
        job.set_progress(5, 'Stopping Active Directory monitor')
        await self.middleware.call('admonitor.stop')
        await self.middleware.call('etc.generate', 'hostname')
        job.set_progress(10, 'Stopping kerberos service')
        await self.middleware.call('kerberos.stop')
        job.set_progress(20, 'Reconfiguring SMB.')
        await self.synchronize()
        await self.middleware.call('idmap.synchronize')
        await self.middleware.call('service.stop', 'cifs')
        job.set_progress(40, 'Reconfiguring pam and nss.')
        await self.middleware.call('etc.generate', 'pam')
        await self.set_state(DSStatus['DISABLED'].name)
        job.set_progress(60, 'clearing caches.')
        await self.middleware.call('service.stop', 'dscache')
        smb_ha_mode = await self.middleware.call('smb.reset_smb_ha_mode')
        if smb_ha_mode == 'CLUSTERED':
            job.set_progress(70, 'Propagating changes to cluster.')
            cl_reload = await self.middleware.call('clusterjob.submit', 'activedirectory.cluster_reload', 'STOP')
            await cl_reload.wait()

        await self.middleware.call('service.start', 'cifs')
        await self.set_state(DSStatus['DISABLED'].name)
        job.set_progress(100, 'Active Directory stop completed.')

    @private
    async def cluster_reload(self, action):
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('service.restart', 'idmap')
        await self.middleware.call('service.restart', 'cifs')
        verb = "start" if action == 'START' else "stop"
        await self.middleware.call(f'kerberos.{verb}')
        await self.middleware.call(f'service.{verb}', 'dscache')
        if action == 'LEAVE':
            with contextlib.suppress(FileNotFoundError):
                os.unlink('/etc/krb5.keytab')

    @private
    async def validate_credentials(self, ad=None):
        """
        Kinit with user-provided credentials is sufficient to determine
        whether the credentials are good. A testbind here is unnecessary.
        """
        if await self.middleware.call('kerberos._klist_test'):
            # Short-circuit credential validation if we have a valid tgt
            return

        if ad is None:
            ad = await self.middleware.call('activedirectory.config')

        payload = {
            'dstype': DSType.DS_TYPE_ACTIVEDIRECTORY.name,
            'conf': {
                'bindname': ad['bindname'],
                'bindpw': ad['bindpw'],
                'domainname': ad['domainname'],
                'kerberos_principal': ad['kerberos_principal'],
            }
        }
        cred = await self.middleware.call('kerberos.get_cred', payload)
        await self.middleware.call('kerberos.do_kinit', {'krb5_cred': cred})
        return

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
    async def _net_ads_join(self, ad=None):
        await self.middleware.call("kerberos.check_ticket")
        if ad is None:
            ad = await self.config()

        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-U', ad['bindname'],
            '-d', '5',
            'ads', 'join'
        ]

        if ad['createcomputer']:
            cmd.append(f'createcomputer={ad["createcomputer"]}')

        cmd.append(ad['domainname'])
        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            await self.set_state(DSStatus['FAULTED'].name)
            await self._parse_join_err(netads.stdout.decode().split(':', 1))

    @private
    async def _net_ads_testjoin(self, workgroup, ad=None):
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
        if ad is None:
            ad = await self.config()

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

    @accepts(Str('domain', default=''))
    @returns(Dict(
        IPAddr('LDAP server'),
        Str('LDAP server name'),
        Str('Realm'),
        LDAP_DN('Bind Path'),
        Int('LDAP port'),
        Int('Server time'),
        IPAddr('KDC server'),
        Int('Server time offset'),
        Int('Last machine account password change')
    ))
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
        cmd = [SMBCmd.NET.value, '--json', 'ads', 'info']
        if domain:
            cmd.extend(['-S', domain])

        netads = await run(cmd, check=False)
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
    async def set_ntp_servers(self):
        """
        Appropriate time sources are a requirement for an AD environment. By default kerberos authentication
        fails if there is more than a 5 minute time difference between the AD domain and the member server.
        """
        ntp_servers = await self.middleware.call('system.ntpserver.query')
        ntp_pool = 'debian.pool.ntp.org'
        default_ntp_servers = list(filter(lambda x: ntp_pool in x['address'], ntp_servers))
        if len(ntp_servers) != 3 or len(default_ntp_servers) != 3:
            return

        try:
            dc_info = await self.lookup_dc()
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
    async def lookup_dc(self, domain=None):
        if domain is None:
            domain = (await self.config())['domainname']

        lookup = await run([SMBCmd.NET.value, '--json', '-S', domain, 'ads', 'lookup'], check=False)
        if lookup.returncode != 0:
            raise CallError("Failed to look up Domain Controller information: "
                            f"{lookup.stderr.decode().strip()}")

        out = json.loads(lookup.stdout.decode())
        return out

    @accepts(Ref('kerberos_username_password'))
    @job(lock="AD_start_stop")
    async def leave(self, job, data):
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

        ad['bindname'] = data.get("username", "")
        ad['bindpw'] = data.get("password", "")
        ad['kerberos_principal'] = ''

        payload = {
            'dstype': DSType.DS_TYPE_ACTIVEDIRECTORY.name,
            'conf': {
                'bindname': data.get('username', ''),
                'bindpw': data.get('password', ''),
                'domainname': ad['domainname'],
                'kerberos_principal': '',
            }
        }

        job.set_progress(5, 'Obtaining kerberos ticket for privileged user.')
        cred = await self.middleware.call('kerberos.get_cred', payload)
        await self.middleware.call('kerberos.do_kinit', {'krb5_cred': cred})

        job.set_progress(10, 'Leaving Active Directory domain.')
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-U', data['username'],
            'ads', 'leave',
        ]
        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            self.logger.warning("Failed to leave domain: %s", netads.stderr.decode())

        job.set_progress(20, 'Removing kerberos keytab and realm.')
        krb_princ = await self.middleware.call(
            'kerberos.keytab.query',
            [('name', '=', 'AD_MACHINE_ACCOUNT')]
        )
        if krb_princ:
            await self.middleware.call('kerberos.keytab.direct_delete', krb_princ[0]['id'])

        if ad['kerberos_realm']:
            try:
                await self.middleware.call('kerberos.realm.direct_delete', ad['kerberos_realm'])
            except MatchNotFound:
                pass

        if netads.returncode == 0 and smb_ha_mode != 'CLUSTERED':
            try:
                pdir = await self.middleware.call("smb.getparm", "private directory", "GLOBAL")
                ts = time.time()
                os.rename(f"{pdir}/secrets.tdb", f"{pdir}/secrets.tdb.bak.{int(ts)}")
                await self.middleware.call("directoryservices.backup_secrets")
            except Exception:
                self.logger.debug("Failed to remove stale secrets file.", exc_info=True)

        job.set_progress(30, 'Clearing local Active Directory settings.')
        payload = {
            'enable': False,
            'site': None,
            'kerberos_realm': None,
            'kerberos_principal': '',
            'domainname': '',
        }
        new = await self.middleware.call('activedirectory.direct_update', payload)
        await self.set_state(DSStatus['DISABLED'].name)

        job.set_progress(40, 'Flushing caches.')
        flush = await run([SMBCmd.NET.value, "cache", "flush"], check=False)
        if flush.returncode != 0:
            self.logger.warning("Failed to flush samba's general cache after leaving Active Directory.")

        with contextlib.suppress(FileNotFoundError):
            os.unlink('/etc/krb5.keytab')

        job.set_progress(50, 'Clearing kerberos configuration and ticket.')
        await self.middleware.call('kerberos.stop')

        job.set_progress(60, 'Regenerating configuration.')
        await self.middleware.call('etc.generate', 'pam')
        await self.synchronize(new)
        await self.middleware.call('idmap.synchronize')

        job.set_progress(60, 'Restarting services.')
        await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('service.restart', 'idmap')
        if smb_ha_mode == 'CLUSTERED':
            job.set_progress(80, 'Propagating changes to other cluster nodes.')
            cl_reload = await self.middleware.call('clusterjob.submit', 'activedirectory.cluster_reload', 'LEAVE')
            await cl_reload.wait()

        job.set_progress(100, 'Successfully left activedirectory domain.')
        return
