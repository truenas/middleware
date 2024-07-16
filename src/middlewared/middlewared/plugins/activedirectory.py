import errno
import json
import ipaddress
import os
import contextlib

from middlewared.plugins.smb import SMBCmd
from middlewared.plugins.kerberos import krb5ccache
from middlewared.schema import (
    accepts, Bool, Dict, Int, IPAddr, LDAP_DN, List, NetbiosName, Ref, returns, Str
)
from middlewared.service import job, private, ConfigService, ValidationError, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.directoryservices.constants import DomainJoinResponse, DSStatus, DSType
from middlewared.utils.directoryservices.krb5_error import KRB5ErrCode, KRB5Error
from middlewared.validators import Range


class ActiveDirectoryModel(sa.Model):
    __tablename__ = 'directoryservice_activedirectory'

    id = sa.Column(sa.Integer(), primary_key=True)
    ad_domainname = sa.Column(sa.String(120))
    ad_bindname = sa.Column(sa.String(120))
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
        cli_namespace = "directory_service.activedirectory"
        role_prefix = "DIRECTORY_SERVICE"

    ENTRY = Dict(
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
        Int('dns_timeout', default=10, validators=[Range(min_=5, max_=40)]),
        Str('nss_info', null=True, enum=['TEMPLATE', 'SFU', 'SFU20', 'RFC2307']),
        Str('createcomputer'),
        NetbiosName('netbiosname'),
        NetbiosName('netbiosname_b'),
        List('netbiosalias', items=[NetbiosName('alias')]),
        Bool('enable'),
        register=True
    )

    @private
    async def ad_extend(self, ad):
        smb = await self.middleware.call('smb.config')

        ad.update({
            'netbiosname': smb['netbiosname_local'],
            'netbiosalias': smb['netbiosalias']
        })

        if ad.get('nss_info'):
            ad['nss_info'] = ad['nss_info'].upper()
        else:
            ad['nss_info'] = 'TEMPLATE'

        if ad.get('kerberos_realm') and type(ad['kerberos_realm']) is dict:
            ad['kerberos_realm'] = ad['kerberos_realm']['id']

        return ad

    @private
    async def ad_compress(self, ad):
        """
        Convert kerberos realm to id. Force domain to upper-case. Remove
        foreign entries.
        kinit will fail if domain name is lower-case.
        """
        for key in ['netbiosname', 'netbiosname_b', 'netbiosalias', 'bindpw']:
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
        must_update = False
        for key in ['netbiosname', 'netbiosalias']:
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

        await self.middleware.call('smb.update', {
            'netbiosname': new['netbiosname'],
            'netbiosalias': new['netbiosalias']
        })

    @private
    async def common_validate(self, new, old, verrors):
        try:
            if not (await self.middleware.call('activedirectory.netbiosname_is_ours', new['netbiosname'], new['domainname'], new['dns_timeout'])):
                verrors.add(
                    'activedirectory_update.netbiosname',
                    f'NetBIOS name [{new["netbiosname"]}] appears to be in use by another computer in Active Directory DNS. '
                    'Further investigation and DNS corrections will be required prior to using the aforementioned name to '
                    'join Active Directory.'
                )
        except CallError:
            pass

        if new['kerberos_realm'] and new['kerberos_realm'] != old['kerberos_realm']:
            realm = await self.middleware.call('kerberos.realm.query', [("id", "=", new['kerberos_realm'])])
            if not realm:
                verrors.add(
                    'activedirectory_update.kerberos_realm',
                    'Invalid Kerberos realm id. Realm does not exist.'
                )

        if not new["enable"]:
            return

        if not await self.middleware.call('pool.query', [], {'count': True}):
            verrors.add(
                "activedirectory_update.enable",
                "Active Directory service may not be enabled before data pool is created."
            )
        ldap_enabled = (await self.middleware.call('ldap.config'))['enable']
        if ldap_enabled:
            verrors.add(
                "activedirectory_update.enable",
                "Active Directory service may not be enabled while LDAP service is enabled."
            )
        if new["enable"] and old["enable"] and new["kerberos_realm"] != old["kerberos_realm"]:
            verrors.add(
                "activedirectory_update.kerberos_realm",
                "Kerberos realm may not be altered while the AD service is enabled. "
                "This is to avoid introducing possible configuration errors that may result "
                "in a production outage."
            )
        if not new.get("bindpw") and not new["kerberos_principal"]:
            verrors.add(
                "activedirectory_update.bindname",
                "Bind credentials or kerberos keytab are required to join an AD domain."
            )
        if new.get("bindpw") and new["kerberos_principal"]:
            verrors.add(
                "activedirectory_update.kerberos_principal",
                "Simultaneous keytab and password authentication are not permitted."
            )
        if not new["domainname"]:
            verrors.add(
                "activedirectory_update.domainname",
                "AD domain name is required."
            )

        if new['allow_dns_updates']:
            ha_mode = await self.middleware.call('smb.get_smb_ha_mode')

            if ha_mode == 'UNIFIED':
                if await self.middleware.call('failover.status') != 'MASTER':
                    return

            smb = await self.middleware.call('smb.config')
            addresses = await self.middleware.call(
                'activedirectory.get_ipaddresses', new, smb, ha_mode
            )

            if not addresses:
                verrors.add(
                    'activedirectory_update.allow_dns_updates',
                    'No server IP addresses passed DNS validation. '
                    'This may indicate an improperly configured reverse zone. '
                    'Review middleware log files for details regarding errors encountered.',
                )

            for a in addresses:
                addr = ipaddress.ip_address(a)
                if addr.is_reserved:
                    verrors.add(
                        'activedirectory_update.allow_dns_updates',
                        f'{addr}: automatic DNS update would result in registering a reserved '
                        'IP address. Users may disable automatic DNS updates and manually '
                        'configure DNS A and AAAA records as needed for their domain.'
                    )

                if addr.is_loopback:
                    verrors.add(
                        'activedirectory_update.allow_dns_updates',
                        f'{addr}: automatic DNS update would result in registering a loopback '
                        'address. Users may disable automatic DNS updates and manually '
                        'configure DNS A and AAAA records as needed for their domain.'
                    )

                if addr.is_link_local:
                    verrors.add(
                        'activedirectory_update.allow_dns_updates',
                        f'{addr}: automatic DNS update would result in registering a link-local '
                        'address. Users may disable automatic DNS updates and manually '
                        'configure DNS A and AAAA records as needed for their domain.'
                    )

                if addr.is_multicast:
                    verrors.add(
                        'activedirectory_update.allow_dns_updates',
                        f'{addr}: automatic DNS update would result in registering a multicast '
                        'address. Users may disable automatic DNS updates and manually '
                        'configure DNS A and AAAA records as needed for their domain.'
                    )

    @accepts(Ref('activedirectory_update'))
    @returns(Ref('activedirectory_update'))
    @job(lock="AD_start_stop")
    async def do_update(self, job, data):
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
            if await self.middleware.call('failover.licensed'):
                if await self.middleware.call('systemdataset.is_boot_pool'):
                    raise ValidationError(
                        'activedirectory.enable',
                        'Active Directory may not be enabled while '
                        'system dataset is on the boot pool'
                    )

        if new['enable'] and old['enable']:
            permitted_keys = [
                'verbose_logging',
                'use_default_domain',
                'allow_trusted_doms',
                'disable_freenas_cache',
                'restrict_pam',
                'timeout',
                'dns_timeout'
            ]
            for entry in old.keys():
                if entry not in new or entry in permitted_keys:
                    continue

                if new[entry] != old[entry]:
                    raise ValidationError(
                        f'activedirectory.{entry}',
                        'Parameter may not be changed while the Active Directory service is enabled.'
                    )

        elif new['enable'] and not old['enable']:
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
                await self.middleware.call(
                    'activedirectory.check_nameservers',
                    new['domainname'],
                    new['site'],
                    new['dns_timeout']
                )
            except CallError as e:
                raise ValidationError(
                    'activedirectory.domainname',
                    e.errmsg
                )

            try:
                await self.validate_credentials(new, domain_info['KDC server'])
            except KRB5Error as e:
                # initially assume the validation error will be
                # about the actual password used
                if new['kerberos_principal']:
                    key = 'activedirectory.kerberos_principal'
                else:
                    key = 'activedirectory.bindpw'

                match e.krb5_code:
                    case KRB5ErrCode.KRB5_LIBOS_CANTREADPWD:
                        if key == 'activedirectory.kerberos_principal':
                            msg = 'Kerberos keytab is no longer valid.'
                        else:
                            msg = f'Active Directory account password for user {new["bindname"]} is expired.'
                    case KRB5ErrCode.KRB5KDC_ERR_CLIENT_REVOKED:
                        msg = 'Active Directory account is locked.'
                    case KRB5ErrCode.KRB5_CC_NOTFOUND:
                        if key == 'activedirectory.kerberos_principal':
                            # When we kinit we try to regenerate keytab if the principal
                            # isn't present in it. If we hit this point it means that user
                            # has been tweaking the system-managed keytab in interesting ways.
                            choices = await self.middleware.call(
                                'kerberos.keytab.kerberos_principal_choices'
                            )
                            msg = (
                                'System keytab lacks an entry for the specified kerberos principal. '
                                f'Please select a valid kerberos principal from available choices: {", ".join(choices)}'
                            )
                        else:
                            # This error shouldn't occur if we're trying to get ticket
                            # with username + password combination
                            msg = str(e)
                    case KRB5ErrCode.KRB5KDC_ERR_POLICY:
                        msg = (
                            'Active Directory security policy rejected request to obtain kerberos ticket. '
                            'This may occur if the bind account has been configured to deny interactive '
                            'logons or require two-factor authentication. Depending on organizational '
                            'security policies, one may be required to pre-generate a kerberos keytab '
                            'and upload to TrueNAS server for use during join process.'
                        )
                    case KRB5ErrCode.KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN:
                        # We're dealing with a missing account
                        if key == "activedirectory.bindpw":
                            key = "activedirectory.bindname"

                        msg = (
                            'Client\'s credentials were not found on remote domain controller. The most '
                            'common reasons for the domain controller to return this response is due to a '
                            'typo in the service account name or the service or the computer account being '
                            'deleted from Active Directory.'
                        )
                    case KRB5ErrCode.KRB5KRB_AP_ERR_SKEW:
                        # Domain permitted clock skew may be more restrictive than our basic
                        # check of no greater than 3 minutes.
                        key = 'activedirectory.domainname'
                        msg = (
                            'The time offset between the TrueNAS server and the active directory domain '
                            'controller exceeds the maximum value permitted by the Active Directory '
                            'configuration. This may occur if NTP is improperly configured on the '
                            'TrueNAS server or if the hardware clock on the TrueNAS server is configured '
                            'for a local timezone instead of UTC.'
                        )
                    case KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED:
                        if new['kerberos_principal']:
                            msg = (
                                'Kerberos principal credentials are no longer valid. Rejoining active directory '
                                'may be required.'
                            )
                        else:
                            msg = 'Preauthentication failed. This typically indicates an incorrect bind password.'
                    case _:
                        # Catchall for more kerberos errors. We can expand if needed.
                        msg = str(e)

                raise ValidationError(key, msg)
            except CallError as e:
                # This may be an encapsulated GSSAPI library error
                if e.errno == errno.EINVAL:
                    # special errno set if GSSAPI BadName exception raised
                    if new['kerberos_principal']:
                        raise ValidationError('activedirectory.kerberos_principal', 'Not a valid principal name')
                    else:
                        raise ValidationError('activedirectory.bindname', 'Not a valid username')

                # No meaningful way to convert into a ValidationError, simply re-raise
                raise e from None

        elif not new['enable'] and new.get('bindpw'):
            raise ValidationError(
                'activedirectory.bindpw',
                'The Active Directory bind password is only used when enabling the active '
                'directory service for the first time and is not stored persistently. Therefore it '
                'is only valid when enabling the service.'
            )

        config = await self.ad_compress(new)
        await self.middleware.call('datastore.update', self._config.datastore, new['id'], config, {'prefix': 'ad_'})
        await self.middleware.call('etc.generate', 'smb')

        if not old['enable'] and new['enable']:
            ngc = await self.middleware.call('network.configuration.config')
            if not ngc['domain'] or ngc['domain'] == 'local':
                try:
                    await self.middleware.call(
                        'network.configuration.update',
                        {'domain': new['domainname']}
                    )
                except CallError:
                    self.logger.warning(
                        'Failed to update domain name in network configuration '
                        'to match active directory value of %s', new['domainname'], exc_info=True
                    )

            if not await self.middleware.call(
                'kerberos.check_ticket',
                {'ccache': krb5ccache.SYSTEM.name},
                False
            ):
                await self.middleware.call('kerberos.start')

            try:
                await self.__start(job)
            except Exception as e:
                self.logger.error('Failed to start active directory service. Disabling.')
                await self.middleware.call(
                    'directoryservices.health.set_state',
                    DSType.AD.value, DSStatus.DISABLED.name
                )
                await self.middleware.call(
                    'datastore.update', self._config.datastore, new['id'],
                    {'enable': False}, {'prefix': 'ad_'}
                )
                raise e

        elif not new['enable'] and old['enable']:
            await self.__stop(job, new)

        elif new['enable'] and old['enable']:
            await self.middleware.call('service.restart', 'idmap')

        return await self.config()

    @private
    async def remove_privileges(self, domain_name):
        """
        Remove any auto-granted domain privileges
        """
        existing_privileges = await self.middleware.call(
            'privilege.query',
            [["name", "=", domain_name]]
        )
        if not existing_privileges:
            return

        await self.middleware.call('privilege.delete', existing_privileges[0]['id'])

    async def __start(self, job):
        """
        Start AD service. In 'UNIFIED' HA configuration, only start AD service
        on active storage controller.
        """
        await self.middleware.call('directoryservices.health.set_state', DSType.AD.value, DSStatus.JOINING.name)
        ad = await self.config()
        join_resp = await job.wrap(await self.middleware.call(
            'directoryservices.connection.join_domain', DSType.AD.value, ad['domainname']
        ))

        await self.middleware.call('directoryservices.health.set_state', DSType.AD.value, DSStatus.HEALTHY.name)

        cache_job_id = await self.middleware.call('directoryservices.connection.activate')
        await job.wrap(await self.middleware.call('core.job_wait', cache_job_id))

        if DomainJoinResponse(join_resp) is DomainJoinResponse.PERFORMED_JOIN:
            await self.set_ntp_servers()
            await self.middleware.call('directoryservices.connection.grant_privileges', DSType.AD.value, ad['domainname'])

        await self.middleware.call('directoryservices.restart_dependent_services')

    async def __stop(self, job, config):
        job.set_progress(0, 'Preparing to stop Active Directory service')
        await self.middleware.call(
            'datastore.update', self._config.datastore,
            config['id'], {'ad_enable': False}
        )

        await self.middleware.call('etc.generate', 'hostname')
        job.set_progress(10, 'Stopping kerberos service')
        await self.middleware.call('kerberos.stop')
        job.set_progress(20, 'Reconfiguring SMB.')
        await self.middleware.call('service.stop', 'cifs')
        await self.middleware.call('service.restart', 'idmap')
        job.set_progress(40, 'Reconfiguring pam and nss.')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('directoryservices.health.set_state', DSType.AD.value, DSStatus.DISABLED.name)
        job.set_progress(60, 'clearing caches.')
        await self.middleware.call('directoryservices.cache.abort_refresh')
        await self.middleware.call('service.start', 'cifs')
        job.set_progress(100, 'Active Directory stop completed.')

    @private
    async def validate_credentials(self, ad=None, kdc=None):
        """
        Kinit with user-provided credentials is sufficient to determine
        whether the credentials are good. A testbind here is unnecessary.
        """
        if await self.middleware.call(
            'kerberos.check_ticket',
            {'ccache': krb5ccache.SYSTEM.name},
            False
        ):
            # Short-circuit credential validation if we have a valid tgt
            return

        ad = ad or await self.config()
        payload = {
            'dstype': DSType.AD.value,
            'conf': {
                'bindname': ad.get('bindname', ''),
                'bindpw': ad.get('bindpw', ''),
                'domainname': ad['domainname'],
                'kerberos_principal': ad['kerberos_principal'],
            }
        }
        cred = await self.middleware.call('kerberos.get_cred', payload)
        await self.middleware.call('kerberos.do_kinit', {
            'krb5_cred': cred,
            'kinit-options': {'kdc_override': {'domain': ad['domainname'], 'kdc': kdc}},
        })
        return

    @accepts(Str('domain', default=''), roles=['DIRECTORY_SERVICE_READ'])
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
    async def cache_flush_retry(self, cmd, retry=True):
        rv = await run(cmd, check=False)
        if rv.returncode != 0 and retry:
            await self.middleware.call('idmap.gencache.flush')
            return await self.cache_flush_retry(cmd, False)

        return rv

    @private
    async def lookup_dc(self, domain=None):
        if domain is None:
            domain = (await self.config())['domainname']

        lookup = await self.cache_flush_retry([SMBCmd.NET.value, '--json', '-S', domain, '--realm', domain, 'ads', 'lookup'])
        if lookup.returncode != 0:
            raise CallError("Failed to look up Domain Controller information: "
                            f"{lookup.stderr.decode().strip()}")

        out = json.loads(lookup.stdout.decode())
        return out

    @accepts(Ref('kerberos_username_password'), roles=['DIRECTORY_SERVICE_WRITE'])
    @returns()
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
        if not ad['domainname']:
            raise CallError('Active Directory domain name present in configuration.')

        ad['bindname'] = data.get("username", "")
        ad['bindpw'] = data.get("password", "")
        ad['kerberos_principal'] = ''

        payload = {
            'dstype': DSType.AD.value,
            'conf': {
                'bindname': data.get('username', ''),
                'bindpw': data.get('password', ''),
                'domainname': ad['domainname'],
                'kerberos_principal': '',
            }
        }

        try:
            await self.remove_privileges(ad['domainname'])
        except Exception:
            self.logger.warning('Failed to remove Domain Admins privileges', exc_info=True)

        job.set_progress(5, 'Obtaining kerberos ticket for privileged user.')
        cred = await self.middleware.call('kerberos.get_cred', payload)
        await self.middleware.call('kerberos.do_kinit', {'krb5_cred': cred})

        job.set_progress(10, 'Leaving Active Directory domain.')
        await job.wrap(await self.middleware.call('directoryservices.connection.leave_domain', DSType.AD.value, ad['domainname']))

        job.set_progress(15, 'Removing DNS entries')
        await self.middleware.call('activedirectory.unregister_dns', ad)

        job.set_progress(20, 'Removing kerberos keytab and realm.')
        krb_princ = await self.middleware.call(
            'kerberos.keytab.query',
            [('name', '=', 'AD_MACHINE_ACCOUNT')]
        )
        if krb_princ:
            await self.middleware.call(
                'datastore.delete', 'directoryservice.kerberoskeytab', krb_princ[0]['id']
            )

        if ad['kerberos_realm']:
            try:
                await self.middleware.call(
                    'datastore.delete', 'directoryservice.kerberosrealm', ad['kerberos_realm']
                )
            except MatchNotFound:
                pass

        try:
            await self.middleware.call("directoryservices.secrets.backup")
        except Exception:
            self.logger.debug("Failed to remove stale secrets entries.", exc_info=True)

        job.set_progress(30, 'Clearing local Active Directory settings.')
        payload = {
            'enable': False,
            'site': None,
            'bindname': '',
            'kerberos_realm': None,
            'kerberos_principal': '',
            'domainname': '',
        }
        await self.middleware.call(
            'datastore.update', self._config.datastore,
            ad['id'], payload, {'prefix': 'ad_'}
        )
        await self.middleware.call('directoryservices.health.set_state', DSType.AD.value, DSStatus.DISABLED.name)

        job.set_progress(40, 'Flushing caches.')
        try:
            await self.middleware.call('idmap.gencache.flush')
        except Exception:
            self.logger.warning("Failed to flush cache after leaving Active Directory.", exc_info=True)

        with contextlib.suppress(FileNotFoundError):
            os.unlink('/etc/krb5.keytab')

        job.set_progress(50, 'Clearing kerberos configuration and ticket.')
        await self.middleware.call('kerberos.stop')

        job.set_progress(60, 'Regenerating configuration.')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('etc.generate', 'smb')

        job.set_progress(60, 'Restarting services.')
        await self.middleware.call('service.restart', 'cifs')
        await self.middleware.call('service.restart', 'idmap')
        job.set_progress(100, 'Successfully left activedirectory domain.')
        return
