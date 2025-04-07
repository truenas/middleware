from middlewared.api import api_method
from middlewared.api.current import (
    DirectoryServicesEntry, DirectoryServicesUpdateArgs, DirectoryServicesUpdateResult,
    DirectoryServicesLeaveArgs, DirectoryServicesLeaveResult,
)
from middlewared.service import ConfigService, private, job
from middlewared.service_exception import MatchNotFound, ValidationErrors
from middlewared.utils.directory_services.constants import (
    DSCredType, DomainJoinResponse, DSStatus, DSType
)
from middlewared.utils.directory_services.credential import (
    validate_credential,
)
from middlewared.utils.directory_services.ldap_client import LDAPClientConfig, LdapClient
from middlewared.utils.directory_services.ldap_constants import (
    LDAP_SEARCH_BASES_SCHEMA_NAME, LDAP_PASSWD_MAP_SCHEMA_NAME,
    LDAP_SHADOW_MAP_SCHEMA_NAME, LDAP_GROUP_MAP_SCHEMA_NAME,
    LDAP_NETGROUP_MAP_SCHEMA_NAME, LDAP_ATTRIBUTE_MAP_SCHEMA_NAME,
)


class DirectoryServicesModel(sa.Model):
    __tablename__ = 'directoryservices'

    id = sa.Column(sa.Integer(), primary_key=True)
    service_type = sa.Column(sa.String(120), nullable=True)
    # Credential-related columns
    cred_type = sa.Column(sa.String(120), nullable=True)
    cred_krb5 = sa.Column(sa.JSON(dict, encrypted=True), nullable=True)
    cred_ldap_plain = sa.Column(sa.JSON(dict, encrypted=True), nullable=True)
    cred_ldap_mtls_cert_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)

    # Common columns for all directory services
    enable = sa.Column(sa.Boolean())
    enable_account_cache = sa.Column(sa.Boolean())
    enable_dns_updates = sa.Column(sa.Boolean())
    timeout = sa.Column(sa.Integer())
    kerberos_realm_id = sa.Column(sa.ForeignKey('directoryservice_kerberosrealm.id', ondelete='SET NULL'),
                                  index=True, nullable=True)

    # Fields used to construct `configuration` dictionary

    # ACTIVEDIRECTORY
    ad_hostname = sa.Column(sa.String(120), nullable=True)
    ad_domain = sa.Column(sa.String(120), nullable=True)
    ad_idmap = sa.Column(sa.JSON(dict, encrypted=True), nullable=True)  # may contain idmap secrets
    ad_site = sa.Column(sa.String(120), nullable=True)
    ad_computer_account_ou = sa.Column(sa.String(120), nullable=True)
    ad_use_default_domain = sa.Column(sa.Boolean())
    ad_enable_trusted_domains = sa.Column(sa.Boolean())
    ad_trusted_domains = sa.Column(sa.JSON(list, encrypted=True), nullable=True)  # may contain idmap secrets

    # IPA
    ipa_hostname = sa.Column(sa.String(120), nullable=True)
    ipa_domain = sa.Column(sa.String(120), nullable=True)
    ipa_target_server = sa.Column(sa.String(120), nullable=True)
    ipa_basedn = sa.Column(sa.String(120), nullable=True)
    ipa_smb_domain = sa.Column(sa.JSON(dict), nullable=True)
    ipa_validate_certificates = sa.Column(sa.Boolean())

    # LDAP
    ldap_server_urls = sa.Column(sa.JSON(list, encrypted=True), nullable=True)
    ldap_starttls = sa.Column(sa.Boolean()) 
    ldap_server_basedn = sa.Column(sa.String(120), nullable=True)
    ldap_validate_certificates = sa.Column(sa.Boolean())
    ldap_schema = sa.Column(sa.String(120), nullable=True)
    # search_bases
    ldap_base_user = sa.Column(sa.String(256), nullable=True)
    ldap_base_group = sa.Column(sa.String(256), nullable=True)
    ldap_base_netgroup = sa.Column(sa.String(256), nullable=True)
    # attribute_maps -> passwd
    ldap_user_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_user_name = sa.Column(sa.String(256), nullable=True)
    ldap_user_uid = sa.Column(sa.String(256), nullable=True)
    ldap_user_gid = sa.Column(sa.String(256), nullable=True)
    ldap_user_gecos = sa.Column(sa.String(256), nullable=True)
    ldap_user_home_directory = sa.Column(sa.String(256), nullable=True)
    ldap_user_shell = sa.Column(sa.String(256), nullable=True)
    # attribute_maps -> shadow
    ldap_shadow_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_last_change = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_min = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_max = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_warning = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_inactive = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_expire = sa.Column(sa.String(256), nullable=True)
    # attribute_maps -> group
    ldap_group_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_group_gid = sa.Column(sa.String(256), nullable=True)
    ldap_group_member = sa.Column(sa.String(256), nullable=True)
    # attribute_maps -> netgroup
    ldap_netgroup_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_member = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_triple = sa.Column(sa.String(256), nullable=True)
    ldap_auxiliary_parameters = sa.Column(sa.TEXT(), nullable=True)


# Keys from datastore that can be presented directly in extend method
DATSTORE_CONFIG_ITEMS = frozenset([
    'id', 'service_type', 'enable', 'enable_account_cache', 'enable_dns_updates',
    'timeout',
])

AD_CONFIG_ITEMS = frozenset([
    'ad_hostname', 'ad_domain', 'ad_idmap', 'ad_site', 'ad_computer_account_ou',
    'ad_use_default_domain', 'ad_enable_trusted_domains', 'ad_trusted_domains',
])

IPA_CONFIG_ITEMS = frozenset([
    'ipa_hostname', 'ipa_target_server', 'ipa_domain', 'ipa_basedn', 'ipa_validate_certificates', 'ipa_smb_domain'
])

LDAP_CONFIG_ITEMS = frozenset([
    'ldap_server_urls', 'ldap_basedn', 'ldap_validate_certificates', 'ldap_schema', 'ldap_auxiliary_parameters',
    'ldap_starttls'
])

NULL_CREDENTIAL = {
    'cred_type': None,
    'cred_krb5': None,
    'cred_ldap_plain': None,
    'cred_ldap_mtls': None
}

SCHEMA = 'directoryservices.update'
KRB_SRV = '_kerberos._tcp.'


class DirectoryServices(ConfigService):
    class Config:
        service = 'directoryservices'
        cli_namespace = 'directory_service'
        datastore = 'directoryservices'
        datastore_extend = 'directoryservices.extend'

    @private
    async def extend_cred(self, data, config_out):
        """ Convert stored datastore credential information into expected dict
        for API response """
        match data['cred_type']:
            case 'KERBEROS_USER' | 'KERBEROS_PRINCIPAL':
                config_out['credential'] = data['cred_krb5'] 
            case 'LDAP_PLAIN':
                config_out['credential'] = data['cred_ldap_plain']
            case 'LDAP_ANONYMOUS':
                config_out['credential'] = {
                    'credential_type': 'LDAP_ANONYMOUS'
                }
            case 'LDAP_MTLS':
                config_out['credential'] = {
                    'credential_type': 'LDAP_MTLS',
                    'client_certificate': data['cred_ldap_mtls_cert']['cert_name'] 
                }
            case: _:
                config_out['credential'] = None
                
    @private
    async def extend_ad(self, data, config_out):
        """ Extend with AD columns if server_type is AD """
        assert data['server_type'] == 'ACTIVEDIRECTORY'
        for key in AD_CONFIG_ITEMS:
            # strip off `ad_` prefix
            config_out[key[3:]] = data[key]

    @private
    async def extend_ipa(self, data, config_out):
        """ Extend with IPA columns if server_type is IPA """
        assert data['server_type'] == 'IPA'
        for key in IPA_CONFIG_ITEMS:
            # strip off `ipa_` prefix
            config_out[key[4:]] = data[key]

    @private
    async def extend_ldap(self, data, config_out):
        """ Extend with LDAP columns if server_type is LDAP """
        assert data['server_type'] == 'LDAP'
        for key in LDAP_CONFIG_ITEMS:
            # strip off `ldap_` prefix
            config_out[key[5:]] = data[key]

        config_out.update({'search_bases': {}, 'attribute_maps': {
            'passwd': {}, 'shadow': {}, 'group': {}, 'netgroup': {}
        }})

        # Add search bases:
        for key, value in data.items():
            if key.startswith('ldap_base_'):
                config_out[LDAP_SEARCH_BASES_SCHEMA_NAME][key[len('ldap_base_'):]] = value
            elif key.startswith('ldap_user_'):
                target = key[len('ldap_user_'):]
                config_out[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_PASSWD_MAP_SCHEMA_NAME][target] = value
            elif key.startswith('ldap_shadow_'):
                target = key[len('ldap_shadow_'):]
                config_out[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_SHADOW_MAP_SCHEMA_NAME][target] = value
            elif key.startswith('ldap_group_'):
                target = key[len('ldap_group_'):]
                config_out[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_GROUP_MAP_SCHEMA_NAME][target] = value
            elif key.startswith('ldap_netgroup_'):
                target = key[len('ldap_netgroup_'):]
                config_out[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_NETGROUP_MAP_SCHEMA_NAME][target] = value

    @private
    async def extend(self, data):
        config = {key: data[key] for key in DATSTORE_CONFIG_ITEMS}
        if kerberos_realm_info := data.pop('kerberos_realm_id'):
            config['kerberos_realm'] = kerberos_realm_info['krb_realm']
        else:
            config['kerberos_realm'] = None

        await self.extend_cred(data, config)

        match data['service_type']:
            case 'ACTIVEDIRECTORY':
                await self.extend_ad(data, config)
            case 'IPA':
                await self.extend_ipa(data, config)
            case 'LDAP':
                await self.extend_ldap(data, config)
            case _:
                # No configured DS type so remove some irrelevant
                # items
                config.update({
                    'enable': False,
                    'credential': None,
                    'configuration': None
                })

        return config

    @private
    def compress_cred(self, data, config_out):
        datastore_cred = NULL_CREDENTIAL.copy()

        if data['credential'] is None:
            config_out.update(datastore_cred)
            return

        datastore_cred['cred_type'] = data['credential']['credential_type']

        match data['credential']['credential_type']:
            case 'KERBEROS_USER' | 'KERBEROS_PRINCIPAL':
                datastore_cred['cred_krb5'] = data['credential'] 
            case 'LDAP_PLAIN':
                datastore_cred['cred_ldap_plain'] = data['credential']
            case 'LDAP_ANONYMOUS':
                pass
            case 'LDAP_MTLS':
                cert_id = self.middleware.call('certificate.query', [
                    ['cert_name', '=', data['credential']['client_certificate']]
                ], {'get': True})
                datastore_cred['cred_ldap_mtls_cert_id'] = cert_id
            case _:
                raise ValueError(f'{data["credential"]["credential_type"]}: unhandled credential type')

         config_out.update(datastore_cred)

    @private
    def compress_config_ad(self, data, config_out):
        for key in AD_CONFIG_ITEMS:
            # slice off "ad_"
            config_out[key] = data[key[3:]]

    @private
    def compress_config_ipa(self, data, config_out):
        for key in IPA_CONFIG_ITEMS:
            # slice off "ipa_"
            config_out[key] = data[key[4:]]

    @private
    def compress_config_ldap(self, data, config_out):
        for key in LDAP_CONFIG_ITEMS:
            # slice off "ldap_"
            config_out[key] = data[key[5:]]

        for key, value in data['configuration'][LDAP_SEARCH_BASES_SCHEMA_NAME]:
            config_out[f'ldap_base_{key}'] = value

        for key, value in data['configuration'][LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_PASSWD_MAP_SCHEMA_NAME]:
            config_out[f'ldap_user_{key}'] = value

        for key, value in data['configuration'][LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_SHADOW_MAP_SCHEMA_NAME]:
            config_out[f'ldap_shadow_{key}'] = value

        for key, value in data['configuration'][LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_GROUP_MAP_SCHEMA_NAME]:
            config_out[f'ldap_group_{key}'] = value

        for key, value in data['configuration'][LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_NETGROUP_MAP_SCHEMA_NAME]:
            config_out[f'ldap_netgroup_{key}'] = value

    @private
    def compress_service_config(self, data, config_out):
        match data['service_type']:
            case 'ACTIVEDIRECTORY':
                self.compress_config_ad(data, config_out)
            case 'IPA':
                self.compress_config_ipa(data, config_out)
            case 'LDAP':
                self.compress_config_ldap(data, config_out)
            case None:
                pass
            case _:
                raise ValueError(f'{data["service_type"]}: unhandled service type')

    @private
    def compress(self, data):
        config = {key: data[key] for key in DATSTORE_CONFIG_ITEMS}
        if data['kerberos_realm']:
            config['kerberos_realm_id'] = self.middleware.call_sync(
                'kerberos.realm.query',
                [['realm', '=', data['kerberos_realm']]],
                {'get': True}
            )['id']

        self.compress_cred(data, config)
        self.compress_service_config(data, config)
        return config

    @private
    def common_validation(self, old, new, verrors):

        # Most changes should not be done while we're enabled as they can result
        # in a production outage that is unacceptable in enterprise environments
        if old['enable'] and new['enable']:
            if old['service_type'] != new['service_type']:
                verrors.add(
                    f'{SCHEMA}.service_type',
                    'Service type for directory services may not be changed while '
                    'directory services are enabled'
                )

            if old['configuration'] != new['configuration']:
                verrors.add(
                    f'{SCHEMA}.configuration',
                    'Permitted changes while directory services are enabled are limited '
                    'to account caching, DNS updates, and timeouts. All other changes should '
                    'be performed with directory services disabled and during a maintenance '
                    'window as the changes may result in a temporary production outage.'
                )

            if new['kerberos_realm'] != old['kerberos_realm']:
                verrors.add(
                    f'{SCHEMA}.kerberos_realm',
                    'Kerberos realm may not be changed while directory service is enabled. '
                )

        if new['kerberos_realm']:
            try:
                self.middleware.call_sync('kerberos.realm.query', [['realm', '=', new['kerberos_realm']]], {'get': True})
            except MatchNotFound:
                verrors.add(f'{SCHEMA}.kerberos_realm', 'Unknown kerberos realm')

        if new['credential']['credential_type'] == DSCredType.LDAP_MTLS:
            cert_name = new['credential']['client_certificate']
            try:
                self.middleware.call_sync('certificate.query', [['cert_name', '=', cert_name]], {'get': True})
            except MatchNotFound:
                verrors.add(f'{SCHEMA}.credential.client_certificate', 'Unknown client certificate.')

        if not new['enable'] and new['credential'] and new['credential']['credential_type'] == DSCredType.KERBEROS_USER:
            if new['service_type'] in (DSType.AD.value, DSType.IPA.value):
                # Avoid storing priviledged credentials on disk
                verrors.add(
                    f'{SCHEMA}.credential.credential_type', 
                    'Kerberos user credentials may not be stored for disabled directory services '
                    'when the directory service type is IPA or Active Directory.'
                )

    @api_method(DirectoryServicesEntry, LDAPClientConfig, private=True)
    def dsconfig_to_ldap_client_config(self, data):
        if not data['enable']:
            raise CallError('Directory services are not enabled')

        out = {
            'server_urls': None,
            'basedn': None,
            'credential': data['credential'],
            'validate_certificates': True,
            'starttls': False,
            'timeout': data['timeout']
        }

        match data['service_type']:
            case DSType.IPA.value:
                if data['credential']['credential_type'].startswith('KERBEROS'):
                    out['server_urls'] = [f'ldap://{data["configuration"]["target_server"]}']
                else:
                    out['server_urls'] = [f'ldaps://{data["configuration"]["target_server"]}']
                out['basedn'] = data['configuration']['basedn']
                out['validate_certifcates'] = data['configuration']['validate_certificates']
            case DSType.LDAP.value:
                out['sever_urls'] = data['configuration']['server_urls']
                out['basedn'] = data['configuration']['basedn']
                out['validate_certifcates'] = data['configuration']['validate_certificates']
                out['starttls'] = data['configuration']['starttls']
            case _:
                raise CallError('LDAP client not supported for service type')

        return out

    @private
    def validate_kerberos_dns(self, schema, verrors, domain, lifetime=10):
        """ verify minimally that we can resolve kerberos SRV for the domain through all nameservers """
        for entry in self.middleware.call_sync('dns.query'):
            record = f'{KRB_SRV}{domain}.'
            try:
                resp = self.middleware.call_sync('dnsclient.forward_lookup', {
                    'names': [f'{KRB_SRV}{domain}.'],
                    'record_types': ['SRV'],
                    'dns_client_options': {
                        'nameservers': [entry['nameserver']],
                        'lifetime': lifetime, 
                    }
                })
            except Exception:
                self.logger.debug(
                    "%s: DNS forward lookup on %s failed with error",
                    record, entry['nameserver'], exc_info=True
                )
                verrors.add(
                    schema,
                    f'Forward lookup of "{record}" failed with nameserver {entry["nameserver"}. This '
                    'may indicate that the specified nameserver is not a valid nameserver for the domain '
                    f'{domain}.'
                )

    @private
    def validate_dns(self, old, new, verrors, revert):
        schema = f'{SCHEMA}.configuration.domain'
        self.validate_kerberos_dns(schema, verrors, new['configuration']['domain'], new['timeout'])

        if new['force']:
            return

        # Check whether forward lookup of our name works 
        dns_name = f'{new["configuration"]["hostname"]}@{new["configuration"]["domain"]}'
        try:
            dns_addresses = set(x['address'] for x in self.middleware.call_sync('dnsclient.forward_lookup', {
                'names': [dns_name],
                'dns_client_options': {'lifetime': new['timeout']}
            })])
        except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            # No entries for this DNS name. This probably just means we've
            # never joined the domain before
            return

        ips_in_use = set(self.middleware.call_sync('directoryservices.bindip_choices'))
        if not dns_address & ips_in_use:
            verrors.add(
                f'{SCHEMA}.configuration.hostname',
                f'{new["configuration"]["hostname"]}: hostname appears to be in use by another server '
                'in the domain. Further investigation and correction of DNS entries may be requred.'
            )

    @private
    def validate_ldap(self, old, new, verrors, revert):

        ldap_config = dsconfig_to_ldap_client_config(new) 
        host_field = 'server_urls' if new['server_type'] == DSType.LDAP.value else 'target_server' 
        try:
            root = LdapClient.search(ldap_config, '', ldap.scope, '(objectclass=*)')
        except ldap.CONFIDENTIALITY_REQUIRED:
            verrors.add(f'{SCHEMA}.configuration.{host_field}', 'LDAP server requires encrypted transport.')
        except ldap.INVALID_CREDENTIALS:
            verrors.add(
                f'{SCHEMA}.credential.credential_type',
                'LDAP server responded that specified credentials are invalid.'
            )
        except ldap.STRONG_AUTH_NOT_SUPPORTED:
            # Past experience with user tickets has shown this as a common LDAP server response
            # to clients trying to use 
            if new['credential']['credential_type'] == DSCredType.LDAP_MTLS:
                verrors.add(
                    f'{SCHEMA}.credential.credential_type',
                    'LDAP server responded that mutual TLS authentication is not supported'
                )
            else:
                verrors.add(
                    f'{SCHEMA}.credential.credential_type',
                    'LDAP server does not support strong authentication'
                )
        except ldap.SERVER_DOWN:
            # SSL libraries here don't do us a lot of favors. If the certificate is invald or
            # self-signed LDAPS connections will fail with SERVER_DOWN.
            verrors.add(
                f'{SCHEMA}.credential.{host_field}'
                'Unable to contact the remote LDAP server. This may occur if the remote server '
                'is unresponsive or if, in the case of LDAPS, there is a lower level cryptographic '
                'error such as certificate validation failure.'
            )
        except ldap.INVALID_DN_SYNTAX as exc:
            verrors.add(
                f'{SCHEMA}.credential.basedn'
                f'Remote LDAP server returned that a specified DN ({exc[0]["matched"]}) is invalid.'
            )
        except ldap.LOCAL_ERROR as exc:
            info = exc[0].get('info', '')
            desc = exc[0].get('desc', '')
            if "KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN" in info: 
                # Past experience with user tickets has shown this to often be caused by RDNS issues
                verrors.add(
                    f'{SCHEMA}.credential.credential_type',
                    'GSSAPI bind failed with error that client was not found in the kerberos database. '
                    'This may occur if the kerberos library failed to validate the kerberos '
                    'principal through reverse DNS.'
                 )
            else:
                # Another local error (not from libldap)
                verrors.add(f'{SCHEMA}.credential.{host_field}', f'LDAP bind failed with error: {info} {desc}')
        except ldap.LDAPError as exc:
            info = exc[0].get('info', '')
            desc = exc[0].get('desc', '')
            verrors.add(f'{SCHEMA}.credential.{host_field}', f'LDAP bind failed with error: {info} {desc}')
        else:
            # Check for problems in LDAP root. In theory we could check whether the server is
            # IPA based on presence of '389 Project' vendorName, but this would be a bit too agressive
            # and break some legacy users.
            if 'domainControllerFunctionality' in root:
                # Oddly enough in the past some users have tortured our LDAP configuration enough
                # to make it bind to AD and then filed tickets because SMB doesn't work properly
                # so we do a check to make sure they haven't decided to bark up the wrong tree.
                verrors.add(
                    f'{SCHEMA}.server_type'
                    'Remote server is an active directory domain controller. Directory services must '
                    'be enabled with the ACTIVEDIRECTORY service_type in order to join an Active Directory '
                    'domain.'
                )

    @private
    def validate_ipa(self, old, new, verrors, revert):
        self.validate_ldap(old, new, verrors, revert)
        self.validate_dns(old, new, verrors, revert)
        
    @private
    def __revert_changes(self, revert):
        for op in in reversed(revert):
            try:
                self.middleware.call_sync(op['method'], *op['args'])
            except Exception:
                self.logger.warning('Cleanup step on failed directory services update failed', exc_info=True)

    @private
    async def bindip_choices(self):
        if await self.middleware.call('failover.licensed'):
            master, backup, init = await self.middleware.call('failover.vip.get_states')
            return {i['address'] for i in master['failover_virtual_aliases']}

        return {i['address'] for i in await self.middleware.call('interface.ip_in_use')})

    @api_method(
        DirectoryServicesUpdateArgs, DirecroyServicesUpdateResult, 
        roles='DIRECTORY_SERVICES_WRITE',
        audit='Directory Services Update'
    )
    @job(lock='directoryservices_change')
    def update(self, job, data):
        old = self.middleware.call_sync('directoryservices.config')
        new = old | data
        revert = []

        verrors = ValidationErrors()
        self.common_validation(old, new)
        verrors.check()

        if not new['enable']:
            # We'll mostly bypass validation on stopping directory services. Sometimes disabling
            # is a last resort in case of very broken configuration and so we should never stop
            # admin from this.

            compressed = self.compress(new)
            # First write datastore changes
            if new['service_type'] is None:
                # User has basically requested to nuke the settings. We'll oblige.
                self.middleware.call_sync('directoryservices.reset')
            else:
                # Simply apply settings to disable
                self.middleware.call_sync('datastore.update', 'directoryservices', old['id'], compressed)

            if old['enable']:
                job.set_progress(f'Disabling {old["service_type"]}')
                # We used to be enabled, which means we need to apply changes to
                # all relevant etc files
                ds_type = DSType(old['service_type'])
                self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.DISABLED.name)

                job.set_progress('Regenerating configuration files')
                for etc in ds_type.etc_files:
                   self.middleware.call_sync('etc.generate', etc)

                svc = 'idmap' if ds_type == DSType.AD else 'sssd'
                self.middleware.call_sync('service.restart', svc)

                # Now restart any dependent services
                job.set_progress('Restarting dependent services')
                self.middleware.call_sync('directoryservices.restart_dependent_services')

            return self.middleware.call_sync('directoryservices.config')

        # First check that our credential is functional. If the credential type is
        # KERBEROS_USER or KERBEROS_PRINCIPAL then this will also perform a kinit and
        # ensure we have a basic kerberos configuration for a potential domain join
        validate_credential(f'{SCHEMA}.credential', new, verrors, revert)
        if verrors:
            self.__revert_changes(revert)

        verrors.check()

        match new['service_type']:
            case 'ACTIVEDIRECTORY':
                self.validate_dns(old, new, verrors, revert)
            case 'IPA':
                self.validate_ipa(old, new, verrors, revert)
            case 'LDAP':
                self.validate_ldap(old, new, verrors, revert)
            case None:
                # Disabling directory services
                pass
            case _:
                raise ValueError(f'{new["service_type"]}: unexpected service_type')

        if verrors:
            self.__revert_changes(revert)

        verrors.check()

        # At this point we know that our credenitals are good and we can properly bind to directory services
        # We'll commit the changes to the datastore to simplify further directory services ops
        compressed = self.compress(new)
        self.middleware.call_sync('datastore.update', 'directoryservices', old['id'], compressed)

        # Prepare to revert datastore changes if it blows up on us
        revert.append({'method': 'datastore.update', 'args': ['directoryservices', old['id'], self.compress(old)]})
        ds_type = DSType(new['service_type'])

        if old['enable']:
            # We've already successully joined in the past. Simply regenerate configuration and restart services.
            job.set_progress('Restarting services')
            for etc in ds_type.etc_files:
                self.middleware.call_sync('etc.generate', etc)

            svc = 'idmap' if ds_type == DSType.AD else 'sssd'
            self.middleware.call_sync('service.restart', svc)
            self.middleware.call_sync('directoryservices.restart_dependent_services')
            try:
                # Perform a sanity check that these changes didn't totally break us.
                self.middleware.call_sync('directoryservices.health.recover')
            except Exception:
                # Try to get back to where we were before these ill-conceived changes
                job.set_progress('Health check failed. Reverting changes.')
                self.__revert_changes(revert)
                for etc in ds_type.etc_files:
                    self.middleware.call_sync('etc.generate', etc)

                self.middleware.call_sync('service.restart', ds_service)
                raise

            return self.middleware.call_sync('directoryservices.config')

        # First perform any relevant join operations.
        self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.JOINING.name) 
        join_resp = DomainJoinResponse.ALREADY_JOINED.value  # This is for LDAP DS (join doesn't exist) 

        if ds_type in (DSType.AD, DSType.IPA):
            join_job = self.middleware.call_sync(
                'directoryservices.connection.join_domain', ds_type.value, new['configuration']['domain']
            )
            try:
                join_resp = job.wrap(join_job)
            except Exception:
                # We failed to join, revert any changes to datastore
                self.__revert_changes(revert)
                self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.DISABLED.name) 
                for etc in ds_type.etc_files:
                    self.middleware.call_sync('etc.generate', etc)
                raise

        # We either successfully joined or were already joined. Activate the service and fill cache
        self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.HEALTHY.name) 
        cache_job_id = self.middleware.call_sync('directoryservices.connection.activate')
        try:
            job.wrap(self.middleware.call('core.job_wait', cache_job_id)
        except Exception:
            self.logger.warning('Failed to build user and group cache', exc_info=True)

        if DomainJoinResponse(join_resp) is DomainJoinResponse.PERFORMED_JOIN:
            # This is a convenience feature for administrators and failure is considered
            # non-fatal, which is why it is not included in domain join steps.
            self.middleware.call_sync('directoryservices.connection.grant_privileges')

        # When IPA support was first added to TrueNAS we did not persistently store
        # IPA SMB domain information persistently. This means we may need to update the IPA domain
        # information.
        if ds_type is DSType.IPA and new['configuration']['smb_domain'] is None:
            if (smb_domain := self.middleware.call_sync('ipa_get_smb_domain_info')) is not None:
                new['configuration']['smb_domain'] = {
                    'name': smb_domain['netbios_name'],
                    'range_low': smb_domain['range_id_min'],
                    'range_high': smb_domain['range_id_max'],
                    'domain_sid': smb_domain['domain_sid'],
                    'domain_name': smb_domain['domain_name'],
                }
                compressed = self.compress(new)
                self.middleware.call_sync('datastore.update', 'directoryservices', old['id'], compressed)
                # Since we now have inserted the domain information we need to regenerate the SMB config
                self.middleware.call_sync('etc.generate', 'smb')

        self.middleware.call_sync('directoryservices.restart_dependent_services')

        # Final health check before saying we joined successfully
        self.middleware.call_sync('directoryservices.health.recover')
        return self.middleware.call_sync('directoryservices.config')

    @private
    async def reset(self):
        """
        Reset all directory services fields to null / disabled. This is an internal method
        that should not be called by other parts of middleware without careful design and
        consideration as it does not reconfigure running services.
        """
        config = await self.middleware.call('datastore.config', 'directoryservices')
        pk = config.pop('id')

        for key in list(config.keys()):
            if key == 'enable':
                conf[key] = False
            elif key == 'timeout':
                conf[key] = 10
            elif isinstance(config[key], bool):
                config[key] = True
            else:
                config[key] = None

        await self.middleware.call('datastore.update', 'directoryservices', pk, config) 

    @api_method(
        DirectoryServicesLeaveArgs, DirectoryServicesLeaveResult,
        roles='DIRECTORY_SERVICES_WRITE',
        audit='Leaving directory services domain'
    )
    @job(lock='directoryservices_change')
    def leave(self, job, cred):
        revert = []
        verrors = ValidationErrors()

        ds_config = self.middleware.call_sync('directoryservices.config')
        if not ds_config['enable']:
            raise CallError('Directory service must be enabled and healthy prior to leaving domain.')

        # overwrite cred with admin-provided one. We need elevated permissions to do this
        ds_config['credentials'] = cred

        ds_type = DSType(ds_config['service_type'])
        if ds_type not in(DSType.IPA, DSType.AD):
            raise CallError('Directory service type does not support leave operations')

        validate_credential(f'directoryservices.leave_domain', , verrors, revert)
        if verrors:
            self.__revert_changes(revert)

        verrors.check()

        # We've successfully managed to kinit for domain with hopefully an admin credential
        try:
            job.wrap_sync(self.middleware.call_sync('directoryservices.connection.leave_domain'))
        except Exception:
            # Make sure we nuke our kerberos ticket
            self.__revert_changes(revert)
            raise

        self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.DISABLED.name)
        job.set_progress('Restarting services')
        self.middleware.call_sync('kerberos.stop')

        for etc_file in DSType.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

        if ds_type is DSType.IPA:
            self.middleware.call_sync('service.stop', 'sssd')
            self.middleware.call_sync('service.restart', 'idmap')
        else:
            self.middleware.call_sync('service.restart', 'idmap')

        self.middleware.call_sync('directoryservices.restart_dependent_services')
