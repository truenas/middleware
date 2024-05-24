import os

from middlewared.plugins.kerberos import krb5ccache
from middlewared.schema import (
    accepts, Bool, Dict, Int, List, NetbiosName, Ref, returns, Str
)
from middlewared.service import job, private, ConfigService, ValidationError, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list
from middlewared.utils.directoryservices.ad_constants import (
    MAX_SERVER_TIME_OFFSET
)
from middlewared.utils.directoryservices.constants import DSStatus
from middlewared.plugins.directoryservices_.all import get_enabled_ds, registered_services_obj
from middlewared.plugins.idmap import DSType
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

        if ad.get('kerberos_realm') and type(ad['kerberos_realm']) == dict:
            ad['kerberos_realm'] = ad['kerberos_realm']['id']

        return ad

    @private
    def ad_compress(self, ad):
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
    def update_netbios_data(self, old, new):
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

        self.middleware.call_sync('smb.update', {
            'netbiosname': new['netbiosname'],
            'netbiosalias': new['netbiosalias']
        })

    @private
    def common_validate(self, new, old, verrors):
        try:
            if not self.middleware.call_sync(
                'activedirectory.netbiosname_is_ours',
                new['netbiosname'], new['domainname'], new['dns_timeout']
            ):
                verrors.add(
                    'activedirectory_update.netbiosname',
                    f'NetBIOS name [{new["netbiosname"]}] appears to be in use '
                    'by another computer in Active Directory DNS. Further '
                    'investigation and DNS corrections will be required prior '
                    'to using the aforementioned name to join Active Directory.'
                )
        except CallError:
            pass

        if new['kerberos_realm'] and new['kerberos_realm'] != old['kerberos_realm']:
            realm = self.middleware.call_sync('kerberos.realm.query', [("id", "=", new['kerberos_realm'])])
            if not realm:
                verrors.add(
                    'activedirectory_update.kerberos_realm',
                    'Invalid Kerberos realm id. Realm does not exist.'
                )

        if not new["enable"]:
            return

        if len(self.middleware.call_sync('zfs.pool.query_imported_fast')) < 2:
            verrors.add(
                "activedirectory_update.enable",
                "Active Directory service may not be enabled before data pool is created."
            )

        enabled_ds = get_enabled_ds()
        if enabled_ds and enabled_ds.name != 'activedirectory':
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
            ip_info = registered_services_obj.activedirectory._get_ip_updates(
                f'{new["netbiosname"]}.{new["domainname"]}',
                True
            )

            if not ip_info['to_add']:
                verrors.add(
                    'activedirectory_update.allow_dns_updates',
                    'No server IP addresses passed DNS validation. '
                    'This may indicate an improperly configured reverse zone. '
                    'Review middleware log files for details regarding errors encountered.',
                )

    @accepts(Ref('activedirectory_update'))
    @returns(Ref('activedirectory_update'))
    @job(lock="AD_start_stop")
    def do_update(self, job, data):
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
        old = self.middleware.call_sync('activedirectory.config')
        new = old.copy()
        new.update(data)
        new['domainname'] = new['domainname'].upper()

        try:
            self.update_netbios_data(old, new)
        except Exception as e:
            raise ValidationError('activedirectory_update.netbiosname', str(e))

        self.common_validate(new, old, verrors)
        ds_obj = registered_services_obj.activedirectory
        verrors.check()

        if new['enable']:
            if new['allow_trusted_doms'] and not self.middleware.call_sync('idmap.may_enable_trusted_domains'):
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
            if self.middleware.call_sync('failover.licensed'):
                if self.middleware.call_sync('systemdataset.is_boot_pool'):
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
                domain_info = ds_obj._domain_info(new['domainname'])
            except CallError as e:
                raise ValidationError('activedirectory.domainname', e.errmsg)

            if abs(domain_info['server_time_offset']) > MAX_SERVER_TIME_OFFSET:
                raise ValidationError(
                    'activedirectory.domainname',
                    'Time offset from Active Directory domain exceeds maximum '
                    'permitted value. This may indicate an NTP misconfiguration.'
                )

            try:
                self.middleware.call_sync(
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
                self.validate_credentials(new, domain_info['kdc_server'])
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
                elif msg.endswith('not found in Kerberos database while getting initial credentials'):
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

        elif not new['enable'] and new.get('bindpw'):
            raise ValidationError(
                'activedirectory.bindpw',
                'The Active Directory bind password is only used when enabling the active '
                'directory service for the first time and is not stored persistently. Therefore it '
                'is only valid when enabling the service.'
            )

        config = self.ad_compress(new)
        self.middleware.call_sync('datastore.update', self._config.datastore, new['id'], config, {'prefix': 'ad_'})
        ds_obj.update_config()
        self.middleware.call_sync('etc.generate', 'smb')

        if not old['enable'] and new['enable']:
            ngc = self.middleware.call_sync('network.configuration.config')
            if not ngc['domain'] or ngc['domain'] == 'local':
                # match up our domainname and the global domain name
                try:
                    self.middleware.call_sync(
                        'network.configuration.update',
                        {'domain': new['domainname']}
                    )
                except CallError:
                    self.logger.warning(
                        'Failed to update domain name in network configuration '
                        'to match active directory value of %s', new['domainname'], exc_info=True
                    )

            if not self.middleware.call_sync(
                'kerberos.check_ticket',
                {'ccache': krb5ccache.SYSTEM.name},
                False
            ):
                self.middleware.call_sync('kerberos.start')

            try:
                self.__start(job)
            except Exception:
                self.logger.error(
                    'Failed to start active directory service. Disabling.',
                    exc_info=True
                )
                self.middleware.call_sync(
                    'datastore.update', self._config.datastore, new['id'],
                    {'enable': False}, {'prefix': 'ad_'}
                )
                ds_obj.update_config()
                raise

        elif not new['enable'] and old['enable']:
            self.__stop(job, new)

        elif new['enable'] and old['enable']:
            self.middleware.call_sync('service.restart', 'idmap')

        return self.middleware.call_sync('activedirectory.config')

    def __start(self, job):
        """
        Start AD service. In 'UNIFIED' HA configuration, only start AD service
        on active storage controller.
        """
        ds_obj = get_enabled_ds()
        if ds_obj.name != 'activedirectory':
            # It is not clear how this could happen, but we should fail
            # if the enabled directory service changes between when we update our
            # config to enable AD and then begin starting the service.
            raise CallError('Enabled directory service type is not active directory')

        ad = ds_obj.config
        smb = self.middleware.call_sync('smb.config')
        workgroup = smb['workgroup']

        dc_info = ds_obj._lookup_dc()

        ds_obj.status = DSStatus.JOINING.name
        job.set_progress(0, 'Preparing to join Active Directory')

        if ad['verbose_logging']:
            self.logger.debug('Starting Active Directory service for [%s]', ad['domainname'])

        self.middleware.call_sync('etc.generate', 'hostname')

        # Double-check our stored kerberos configuration and insert
        # our AD realm if it doesn't already exist.
        job.set_progress(5, 'Configuring Kerberos Settings.')
        if not ad['kerberos_realm']:
            try:
                realm_id = self.middleware.call_sync(
                    'kerberos.realm.query',
                    [('realm', '=', ad['domainname'])],
                    {'get': True}
                )['id']
            except MatchNotFound:
                realm_id = self.middleware.call_sync(
                    'datastore.insert', 'directoryservice.kerberosrealm',
                    {'krb_realm': ad['domainname'].upper()}
                )

            self.middleware.call_sync(
                'datastore.update', self._config.datastore, ad['id'],
                {"kerberos_realm": realm_id}, {'prefix': 'ad_'}
            )
            ds_obj.update_config()
            ad = ds_obj.config

        job.set_progress(20, 'Detecting Active Directory Site.')
        # AD site will be None the first time it is configured. We autodetect
        # from the domain controller.
        if not ad['site']:
            # update our site based on client site name. This is used as a
            # hint in alerts to user to make site-specific kerberos configuration.
            ad['site'] = dc_info['client_site_name']

        job.set_progress(30, 'Detecting Active Directory NetBIOS Domain Name.')
        # Set our SMB workgroup to the correct one for the AD domain.
        if workgroup != dc_info['pre-win2k_domain']:
            self.middleware.call_sync('datastore.update', 'services.cifs', smb['id'], {
                'cifs_srv_workgroup': dc_info['pre-win2k_domain']
            })
            workgroup = dc_info['pre-win2k_domain']

        # Ensure smb4.conf has correct workgorup.
        self.middleware.call_sync('etc.generate', 'smb')

        job.set_progress(40, 'Performing testjoin to Active Directory Domain')
        is_joined = ds_obj.test_join(workgroup)
        if not is_joined:
            job.set_progress(50, 'Joining Active Directory Domain')
            self.logger.debug(f"Test join to {ad['domainname']} failed. Performing domain join.")

            domain_info = ds_obj.join(workgroup)
            machine_acct = f'{domain_info["machine_account"]["sAMAccountName"]}@{ad["domainname"]}'

            job.set_progress(75, 'Performing kinit using new computer account.')

            """
            Remove our temporary administrative ticket and replace with machine account.

            Sysvol replication may not have completed (new account only exists on the DC we're
            talking to) and so during this operation we need to hard-code which KDC we use for
            the new kinit.
            """
            self.middleware.call_sync('kerberos.stop')
            cred = self.middleware.call_sync('kerberos.get_cred', {
                'dstype': DSType.DS_TYPE_ACTIVEDIRECTORY.name,
                'conf': {
                    'domainname': ad['domainname'],
                    'kerberos_principal': machine_acct,
                }
            })

            try:
                os.unlink('/etc/krb5.conf')
            except FileNotFoundError:
                pass

            self.middleware.call_sync('kerberos.do_kinit', {
                'krb5_cred': cred,
                'kinit-options': {
                    'kdc_override': {'domain': ad['domainname'], 'kdc': domain_info['kdc_server']}
                }
            })
            self.middleware.call_sync('kerberos.wait_for_renewal')

            # We have our ticket, replace with standard krb5.conf
            self.middleware.call_sync('etc.generate', 'kerberos')

            job.set_progress(80, 'Configuring idmap backend and NTP servers.')
            self.middleware.call_sync('activedirectory.set_ntp_servers')
        else:
            # We are already joined to AD. User may have disabled then re-renabled the plugin
            # Check whether we have valid kerberos principal
            domain_info = ds_obj._domain_info()
            machine_acct = f'{domain_info["machine_account"]["sAMAccountName"]}@{ad["domainname"]}'
            if not ad['kerberos_principal']:
                if not self.middleware.call_sync('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']]):
                    # Force writing of keytab based on stored secrets to our config file.
                    self.middleware.call_sync('activedirectory.check_machine_account_keytab', ad['domainname'])

                self.middleware.call_sync('datastore.update', self._config.datastore, ad['id'], {
                    'kerberos_principal': machine_acct
                }, {'prefix': 'ad_'})

            ds_obj.generate_etc()
            self.middleware.call_sync('service.restart', 'idmap')
            self.middleware.call_sync('directoryservices.restart_dependent_services')
            ds_obj.fill_cache()

        ds_obj.status = DSStatus.HEALTHY.name
        if ad['verbose_logging']:
            self.logger.debug('Successfully started AD service for [%s].', ad['domainname'])

        self.middleware.call_sync('service.reload', 'idmap')
        job.set_progress(100, 'Active Directory start completed.')

    async def __stop(self, job, config):
        job.set_progress(0, 'Preparing to stop Active Directory service')
        job.set_progress(5, 'Stopping Active Directory monitor')
        await self.middleware.call('etc.generate', 'hostname')
        job.set_progress(10, 'Stopping kerberos service')
        await self.middleware.call('kerberos.stop')
        await self.middleware.call('service.restart', 'idmap')
        job.set_progress(40, 'Reconfiguring pam and nss.')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'nss')
        job.set_progress(80, 'Restarting dependent services.')
        await self.middleware.call('directoryservices.restart_dependent_services')
        job.set_progress(100, 'Active Directory stop completed.')

    @private
    def validate_credentials(self, ad=None, kdc=None):
        """
        Kinit with user-provided credentials is sufficient to determine
        whether the credentials are good. A testbind here is unnecessary.
        """
        if self.middleware.call_sync(
            'kerberos.check_ticket',
            {'ccache': krb5ccache.SYSTEM.name},
            False
        ):
            # Short-circuit credential validation if we have a valid tgt
            return

        payload = {
            'dstype': DSType.DS_TYPE_ACTIVEDIRECTORY.name,
            'conf': {
                'bindname': ad.get('bindname', ''),
                'bindpw': ad.get('bindpw', ''),
                'domainname': ad['domainname'],
                'kerberos_principal': ad['kerberos_principal'],
            }
        }
        cred = self.middleware.call_sync('kerberos.get_cred', payload)
        self.middleware.call_sync('kerberos.do_kinit', {
            'krb5_cred': cred,
            'kinit-options': {'kdc_override': {'domain': ad['domainname'], 'kdc': kdc}},
        })

    @private
    def set_ntp_servers(self):
        """
        Appropriate time sources are a requirement for an AD environment. By default kerberos authentication
        fails if there is more than a 5 minute time difference between the AD domain and the member server.
        """
        ds_obj = get_enabled_ds()

        ntp_servers = self.middleware.call_sync('system.ntpserver.query')
        if len(ntp_servers) != 3:
            # admin has already customized NTP servers
            return

        if filter_list(ntp_servers, [['address', '!^', 'debian.pool.ntp.org']]):
            # default NTP servers replaced. skip
            return

        try:
            dc_info = ds_obj._lookup_dc()
        except CallError:
            self.logger.warning("Failed to automatically set time source.", exc_info=True)
            return

        if not dc_info['flags']['is_running_time_services']:
            return

        dc_name = dc_info['information_for_domain_controller']

        try:
            self.middleware.call_sync('system.ntpserver.create', {'address': dc_name, 'prefer': True})
        except Exception:
            self.logger.warning('Failed to configure NTP for the Active Directory domain. Additional '
                                'manual configuration may be required to ensure consistent time offset, '
                                'which is required for a stable domain join.', exc_info=True)

    @accepts(Ref('kerberos_username_password'), roles=['DIRECTORY_SERVICE_WRITE'])
    @returns()
    @job(lock="AD_start_stop")
    def leave(self, job, data):
        """
        Leave Active Directory domain. This will remove computer
        object from AD and clear relevant configuration data from
        the NAS.
        This requires credentials for appropriately-privileged user.
        Credentials are used to obtain a kerberos ticket, which is
        used to perform the actual removal from the domain.
        """
        ds_obj = registered_services_obj.activedirectory
        ad = self.middleware.call_sync('activedirectory.config')
        if not ad['domainname']:
            raise CallError('Active Directory domain name not present in configuration.')

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
        cred = self.middleware.call_sync('kerberos.get_cred', payload)
        self.middleware.call_sync('kerberos.do_kinit', {'krb5_cred': cred})

        job.set_progress(15, 'Leaving active directory domain.')
        ds_obj.leave(data['username'])

        job.set_progress(50, 'Clearing kerberos configuration and ticket.')
        self.middleware.call_sync('kerberos.stop')

        job.set_progress(60, 'Restarting services.')
        self.middleware.call_sync('directoryservices.restart_dependent_services')
        job.set_progress(100, 'Successfully left activedirectory domain.')
