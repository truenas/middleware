import dns
import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    DirectoryServicesEntry,
    DirectoryServicesUpdateArgs, DirectoryServicesUpdateResult,
    DirectoryServicesLeaveArgs, DirectoryServicesLeaveResult,
    DirectoryServicesCertificateChoicesArgs, DirectoryServicesCertificateChoicesResult,
)
from middlewared.plugins.directoryservices_.util_cache import expire_cache
from middlewared.service import ConfigService, private, job
from middlewared.service_exception import CallError, MatchNotFound, ValidationErrors
from middlewared.utils.directoryservices.ad import get_domain_info, lookup_dc
from middlewared.utils.directoryservices.krb5 import ktutil_list_impl
from middlewared.utils.directoryservices.constants import (
    DSCredType, DomainJoinResponse, DSStatus, DSType, DEF_SVC_OPTS
)
from middlewared.utils.directoryservices.credential import (
    validate_credential, validate_ldap_credential,
)
from middlewared.utils.directoryservices.ldap_constants import (
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
    ldap_server_urls = sa.Column(sa.JSON(list), nullable=True)
    ldap_starttls = sa.Column(sa.Boolean())
    ldap_basedn = sa.Column(sa.String(120), nullable=True)
    ldap_validate_certificates = sa.Column(sa.Boolean())
    ldap_schema = sa.Column(sa.String(120), nullable=True)

    # NOTE: search bases and attribute maps are strings because they provide the names of the respective LDAP fields

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
    ldap_auxiliary_parameters = sa.Column(sa.Text(), nullable=True)


# Keys from datastore that can be presented directly in extend method
DATSTORE_CONFIG_ITEMS = frozenset([
    'id', 'service_type', 'enable', 'enable_account_cache', 'enable_dns_updates',
    'timeout',
])

# keys that are unique to particular directory services and presented in `configuration`
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
    'cred_ldap_mtls_cert': None
}

SCHEMA = 'directoryservices.update'
KRB_SRV = '_kerberos._tcp.'  # SRV for kerberos for DNS queries to check our nameservers


class DirectoryServices(ConfigService):
    class Config:
        service = 'directoryservices'
        cli_namespace = 'directory_service'
        datastore = 'directoryservices'
        datastore_extend = 'directoryservices.extend'
        entry = DirectoryServicesEntry
        role_prefix = 'DIRECTORY_SERVICE'

    @private
    async def extend_cred(self, data, config_out):
        """ Convert stored datastore credential information into expected dict
        for API response """
        match data['cred_type']:
            case DSCredType.KERBEROS_USER | DSCredType.KERBEROS_PRINCIPAL:
                config_out['credential'] = data['cred_krb5']
            case DSCredType.LDAP_PLAIN:
                config_out['credential'] = data['cred_ldap_plain']
            case DSCredType.LDAP_ANONYMOUS:
                config_out['credential'] = {
                    'credential_type': DSCredType.LDAP_ANONYMOUS
                }
            case DSCredType.LDAP_MTLS:
                config_out['credential'] = {
                    'credential_type': DSCredType.LDAP_MTLS,
                    'client_certificate': data['cred_ldap_mtls_cert']['cert_name']
                }
            case _:
                config_out['credential'] = None

    @private
    async def extend_ad(self, data, config_out):
        """ Extend with AD columns if service_type is AD """
        assert data['service_type'] == DSType.AD.value
        config_out['configuration'] = {}
        for key in AD_CONFIG_ITEMS:
            # strip off `ad_` prefix
            config_out['configuration'][key.removeprefix('ad_')] = data[key]

    @private
    async def extend_ipa(self, data, config_out):
        """ Extend with IPA columns if service_type is IPA """
        assert data['service_type'] == DSType.IPA.value
        config_out['configuration'] = {}
        for key in IPA_CONFIG_ITEMS:
            # strip off `ipa_` prefix
            config_out['configuration'][key.removeprefix('ipa_')] = data[key]

    @private
    async def extend_ldap(self, data, config_out):
        """ Extend with LDAP columns if service_type is LDAP """
        assert data['service_type'] == DSType.LDAP.value
        config_out['configuration'] = {}
        for key in LDAP_CONFIG_ITEMS:
            # strip off `ldap_` prefix
            config_out['configuration'][key.removeprefix('ldap_')] = data[key]

        config_out['configuration'].update({'search_bases': {}, 'attribute_maps': {
            'passwd': {}, 'shadow': {}, 'group': {}, 'netgroup': {}
        }})

        c = config_out['configuration']
        # Add search bases and attribute maps:
        for key, value in data.items():
            target = key.removeprefix('ldap_')
            if key.startswith('ldap_base_'):
                c[LDAP_SEARCH_BASES_SCHEMA_NAME][target] = value
            elif key.startswith('ldap_user_'):
                c[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_PASSWD_MAP_SCHEMA_NAME][target] = value
            elif key.startswith('ldap_shadow_'):
                c[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_SHADOW_MAP_SCHEMA_NAME][target] = value
            elif key.startswith('ldap_group_'):
                c[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_GROUP_MAP_SCHEMA_NAME][target] = value
            elif key.startswith('ldap_netgroup_'):
                c[LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][LDAP_NETGROUP_MAP_SCHEMA_NAME][target] = value

    @private
    async def extend(self, data):
        config = {key: data[key] for key in DATSTORE_CONFIG_ITEMS}
        if kerberos_realm_info := data.pop('kerberos_realm'):
            config['kerberos_realm'] = kerberos_realm_info['krb_realm']
        else:
            config['kerberos_realm'] = None

        await self.extend_cred(data, config)

        match data['service_type']:
            case DSType.AD.value:
                await self.extend_ad(data, config)
            case DSType.IPA.value:
                await self.extend_ipa(data, config)
            case DSType.LDAP.value:
                await self.extend_ldap(data, config)
            case _:
                # No configured DS type so remove some irrelevant items. We're trying to
                # avoid raising errors in the config method if for some reason there's a
                # garbage value in the database.
                config.update({
                    'enable': False,
                    'credential': None,
                    'configuration': None
                })

        return config

    @private
    def compress_cred(self, data, config_out):
        """ This method converts the `credential` dictionary into relevant database columns. """
        datastore_cred = NULL_CREDENTIAL.copy()

        if data['credential'] is None:
            config_out.update(datastore_cred)
            return

        datastore_cred['cred_type'] = data['credential']['credential_type']

        match data['credential']['credential_type']:
            case DSCredType.KERBEROS_USER | DSCredType.KERBEROS_PRINCIPAL:
                datastore_cred['cred_krb5'] = data['credential']
            case DSCredType.LDAP_PLAIN:
                datastore_cred['cred_ldap_plain'] = data['credential']
            case DSCredType.LDAP_ANONYMOUS:
                pass
            case DSCredType.LDAP_MTLS:
                cert_id = self.middleware.call('certificate.query', [
                    ['cert_name', '=', data['credential']['client_certificate']]
                ], {'get': True})
                datastore_cred['cred_ldap_mtls_cert'] = cert_id
            case _:
                raise ValueError(f'{data["credential"]["credential_type"]}: unhandled credential type')

        config_out.update(datastore_cred)

    @private
    def compress_config_ad(self, data, config_out):
        for key in AD_CONFIG_ITEMS:
            # slice off "ad_"
            config_out[key] = data['configuration'][key.removeprefix('ad_')]

    @private
    def compress_config_ipa(self, data, config_out):
        for key in IPA_CONFIG_ITEMS:
            # slice off "ipa_"
            config_out[key] = data['configuration'][key.removeprefix('ipa_')]

    @private
    def compress_config_ldap(self, data, config_out):
        for key in LDAP_CONFIG_ITEMS:
            # slice off "ldap_"
            config_out[key] = data['configuration'][key.removeprefix('ldap_')]

        for key, value in data['configuration'][LDAP_SEARCH_BASES_SCHEMA_NAME].items():
            config_out[f'ldap_{key}'] = value

        for section in (
            LDAP_PASSWD_MAP_SCHEMA_NAME, LDAP_SHADOW_MAP_SCHEMA_NAME, LDAP_GROUP_MAP_SCHEMA_NAME,
            LDAP_NETGROUP_MAP_SCHEMA_NAME
        ):
            for key, value in data['configuration'][LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][section].items():
                config_out[f'ldap_{key}'] = value

    @private
    def compress_service_config(self, data, config_out):
        match data['service_type']:
            case DSType.AD.value:
                self.compress_config_ad(data, config_out)
            case DSType.IPA.value:
                self.compress_config_ipa(data, config_out)
            case DSType.LDAP.value:
                self.compress_config_ldap(data, config_out)
            case None:
                pass
            case _:
                raise ValueError(f'{data["service_type"]}: unhandled service type')

    @private
    def compress(self, data):
        # first compress the common configuration items
        config = {key: data[key] for key in DATSTORE_CONFIG_ITEMS}

        # we extend the kerberos realm to just its name, but we insert the pk into the database
        if data['kerberos_realm']:
            config['kerberos_realm'] = self.middleware.call_sync(
                'kerberos.realm.query',
                [['realm', '=', data['kerberos_realm']]],
                {'get': True}
            )['id']

        # the `credential` and `configuration` keys in extended data are dictionaries that need
        # to be compressed back down to their constituent database columns.
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
                    'Service type for directory services may not be changed while directory services are enabled'
                )

            if old['configuration'] != new['configuration']:
                verrors.add(
                    f'{SCHEMA}.configuration',
                    'Permitted changes while directory services are enabled are limited to account caching, DNS '
                    'updates, and timeouts. All other changes should be performed with directory services disabled and '
                    'during a maintenance window as the changes may result in a temporary production outage.'
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

        if new['credential'] and new['credential']['credential_type'] == DSCredType.LDAP_MTLS:
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

    @private
    def validate_kerberos_dns(self, schema, verrors, domain, lifetime=10):
        """ verify minimally that we can resolve kerberos SRV for the domain through all nameservers. This is
        important because kerberos by default will try to resolve hostnames and realms through DNS. If a non-domain
        nameserver is present, then it can cause an unexpected production outage."""
        for entry in self.middleware.call_sync('dns.query'):
            record = f'{KRB_SRV}{domain}.'
            try:
                self.middleware.call_sync('dnsclient.forward_lookup', {
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
                    f'Forward lookup of "{record}" failed with nameserver {entry["nameserver"]}. This '
                    'may indicate that the specified nameserver is not a valid nameserver for the domain '
                    f'{domain}.'
                )

    @private
    def validate_dns(self, old, new, verrors, revert):
        """ Check whether nameservers are correct and check whether our proposed hostname is currently in-use
        by another server. The latter check may be skipped if `force` is specified. """
        schema = f'{SCHEMA}.configuration.domain'
        self.validate_kerberos_dns(schema, verrors, new['configuration']['domain'], new['timeout'])

        if new.get('force', False):
            return

        # Check whether forward lookup of our name works
        dns_name = f'{new["configuration"]["hostname"]}@{new["configuration"]["domain"]}'
        try:
            dns_addresses = set(x['address'] for x in self.middleware.call_sync('dnsclient.forward_lookup', {
                'names': [dns_name],
                'dns_client_options': {'lifetime': new['timeout']}
            }))
        except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            # No entries for this DNS name. This probably just means we've
            # never joined the domain before
            return

        ips_in_use = set(self.middleware.call_sync('directoryservices.bindip_choices'))
        if not dns_addresses & ips_in_use:
            verrors.add(
                f'{SCHEMA}.configuration.hostname',
                f'{new["configuration"]["hostname"]}: hostname appears to be in use by another server '
                'in the domain. Further investigation and correction of DNS entries may be required.'
            )

    @private
    def validate_ipa(self, old, new, verrors, revert):
        validate_ldap_credential(SCHEMA, new, verrors, revert)
        self.validate_dns(old, new, verrors, revert)

    @private
    def __revert_changes(self, revert):
        for op in reversed(revert):
            try:
                self.middleware.call_sync(op['method'], *op['args'])
            except Exception:
                self.logger.warning('Cleanup step on failed directory services update failed', exc_info=True)

    @private
    async def bindip_choices(self):
        choices = {}

        if await self.middleware.call('failover.licensed'):
            master, backup, init = await self.middleware.call('failover.vip.get_states')
            for master_iface in await self.middleware.call('interface.query', [["id", "in", master + backup]]):
                for i in master_iface['failover_virtual_aliases']:
                    choices[i['address']] = i['address']

            return choices

        for i in await self.middleware.call('interface.ip_in_use'):
            choices[i['address']] = i['address']

        return choices

    @api_method(
        DirectoryServicesUpdateArgs, DirectoryServicesUpdateResult,
        roles=['DIRECTORY_SERVICE_WRITE'],
        audit='Directory Services Update'
    )
    @job(lock='directoryservices_change')
    def update(self, job, data):
        old = self.middleware.call_sync('directoryservices.config')
        new = old | data
        revert = []  # list of methods and arguments required to revert back to clean state

        verrors = ValidationErrors()
        self.common_validation(old, new, verrors)
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
                job.set_progress(description=f'Disabling {old["service_type"]}')
                # We used to be enabled, which means we need to apply changes to
                # all relevant etc files
                ds_type = DSType(old['service_type'])
                self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.DISABLED.name)

                job.set_progress(description='Regenerating configuration files')
                for etc in ds_type.etc_files:
                    self.middleware.call_sync('etc.generate', etc)

                svc = 'idmap' if ds_type == DSType.AD else 'sssd'
                self.middleware.call_sync('service.control', 'RESTART', svc, DEF_SVC_OPTS).wait_sync(raise_error=True)

                # Now restart any dependent services
                job.set_progress(description='Restarting dependent services')
                self.middleware.call_sync('directoryservices.restart_dependent_services')

            return self.middleware.call_sync('directoryservices.config')

        # Configuration from a different service type should not by default carry over to the new service_type
        # This is a somewhat artificial situation that manual testing can encounter because testers can switch
        # between IPA / AD / OpenLDAP, and we should minimally ensure that invalid config doesn't get carried over.
        if old['service_type'] and old['service_type'] != new['service_type']:
            self.middleware.call_sync('directoryservices.reset')

        if not old['enable'] and new['service_type'] == DSType.AD.value:
            # There may be a stale server affinity in the samba gencache and stale idmappings
            # We should clear these before trying to enable AD
            self.middleware.call_sync('idmap.clear_idmap_cache').wait_sync()

            if old['configuration'] and old['configuration'].get('idmap') != new['configuration']['idmap']:
                # We've changed idmap configuration so we need to expire the directory services cache
                expire_cache()

        # First check that our credential is functional. If the credential type is
        # KERBEROS_USER or KERBEROS_PRINCIPAL then this will also perform a kinit and
        # ensure we have a basic kerberos configuration for a potential domain join
        validate_credential(SCHEMA, new, verrors, revert)
        if verrors:
            self.__revert_changes(revert)

        verrors.check()

        match new['service_type']:
            case DSType.AD.value:
                self.validate_dns(old, new, verrors, revert)
            case DSType.IPA.value:
                self.validate_ipa(old, new, verrors, revert)
            case DSType.LDAP.value:
                # pre-validated when we call validate_credential() above
                pass
            case None:
                # Disabling directory services
                pass
            case _:
                raise ValueError(f'{new["service_type"]}: unexpected service_type')

        if verrors:
            self.__revert_changes(revert)

        verrors.check()

        # If admin specified a realm and we got past credential verification then it was probably
        # not garbage and so it should be inserted.
        if new['kerberos_realm']:
            if not self.middleware.call_sync('kerberos.realm.query', [['realm', '=', new['kerberos_realm']]]):
                realm_id = self.middleware.call_sync(
                    'datastore.insert', 'directoryservice.kerberosrealm',
                    {'krb_realm': new['kerberos_realm']}
                )
                revert.append({'method': 'kerberos.realm.delete', 'args': [realm_id]})

        # At this point we know that our credentials are good and we can properly bind to directory services
        # We'll commit the changes to the datastore to simplify further directory services ops
        compressed = self.compress(new)
        self.middleware.call_sync('datastore.update', 'directoryservices', old['id'], compressed)

        # Prepare to revert datastore changes if it blows up on us
        revert.append({'method': 'datastore.update', 'args': ['directoryservices', old['id'], self.compress(old)]})
        ds_type = DSType(new['service_type'])

        if old['enable']:
            # We've already successfully joined in the past. Simply regenerate configuration and restart services.
            job.set_progress(description='Restarting services')
            for etc in ds_type.etc_files:
                self.middleware.call_sync('etc.generate', etc)

            svc = 'idmap' if ds_type == DSType.AD else 'sssd'
            self.middleware.call_sync('service.control', 'RESTART', svc, DEF_SVC_OPTS).wait_sync(raise_error=True)
            self.middleware.call_sync('directoryservices.restart_dependent_services')
            try:
                # Perform a sanity check that these changes didn't totally break us.
                self.middleware.call_sync('directoryservices.health.recover')
            except Exception:
                # Try to get back to where we were before these ill-conceived changes
                job.set_progress(description='Health check failed. Reverting changes.')
                self.__revert_changes(revert)
                for etc in ds_type.etc_files:
                    self.middleware.call_sync('etc.generate', etc)

                self.middleware.call_sync('service.control', 'RESTART', svc, DEF_SVC_OPTS).wait_sync(raise_error=True)
                raise

            return self.middleware.call_sync('directoryservices.config')

        # First perform any relevant join operations.
        self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.JOINING.name)
        join_resp = DomainJoinResponse.ALREADY_JOINED.value  # This is for LDAP DS (join doesn't exist)

        if ds_type in (DSType.AD, DSType.IPA):
            join_job = self.middleware.call_sync('directoryservices.connection.join_domain', new.get('force', False))
            try:
                join_resp = job.wrap_sync(join_job)
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
            job.wrap_sync(self.middleware.call_sync('core.job_wait', cache_job_id))
        except Exception:
            self.logger.warning('Failed to build user and group cache', exc_info=True)

        if DomainJoinResponse(join_resp) is DomainJoinResponse.PERFORMED_JOIN:
            # This is a convenience feature for administrators and failure is considered
            # non-fatal, which is why it is not included in domain join steps.
            try:
                self.middleware.call_sync(
                    'directoryservices.connection.grant_privileges',
                    ds_type.value,
                    new['configuration']['domain']
                )
            except Exception:
                self.logger.warning('Failed to automatically grant privileges to domain administrators.', exc_info=True)

            # The join process may have updated our configuration
            new = self.middleware.call_sync('directoryservices.config')

        # When IPA support was first added to TrueNAS we did not persistently store IPA SMB domain information.
        # This means we may need to update the IPA domain information.
        if ds_type is DSType.IPA and not new['configuration']['smb_domain']:
            if (smb_domain := self.domain_info()) is not None:
                new['configuration']['smb_domain'] = {
                    'name': smb_domain['netbios_name'],
                    'idmap_backend': 'SSS',
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

        # We may have used our domain secrets to restore the AD machine account keytab
        if ds_type is DSType.AD and new['credential']['credential_type'] == DSCredType.KERBEROS_USER:
            netbiosname = self.middleware.call_sync('smb.config')['netbiosname'].upper()
            principal = None
            for entry in ktutil_list_impl():
                if entry['principal'].startswith(f'{netbiosname}$'):
                    principal = entry['principal']
                    break

            if not principal:
                self.logger.warning('%s: netbiosname not found in keytab file', netbiosname)
                # Make a guess at principal name
                principal = f'{netbiosname}$@{new["configuration"]["domain"]}'

            new['credential'] = {'credential_type': DSCredType.KERBEROS_PRINCIPAL, 'principal': principal}
            compressed = self.compress(new)
            self.middleware.call_sync('datastore.update', 'directoryservices', old['id'], compressed)

        return self.middleware.call_sync('directoryservices.config')

    @private
    def domain_info(self):
        """ Private method to retrieve information about the domain. This is currently consumed
        by CI tests, but may be worth making public. """
        ds_config = self.middleware.call_sync('directoryservices.config')
        if not ds_config['enable']:
            raise CallError('Directory services are not enabled')

        match ds_config['service_type']:
            case DSType.AD.value:
                dom_info = get_domain_info(ds_config['configuration']['domain'])
                dom_info['domain_controller'] = lookup_dc(ds_config['configuration']['domain'])
                return dom_info
            case DSType.IPA.value:
                return self.middleware.call_sync('directoryservices.connection.ipa_get_smb_domain_info')
            case DSType.LDAP.value:
                return None
            case _:
                raise CallError(f'{ds_config["service_type"]}: unexpected service_type')

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
                config[key] = False
            elif key == 'timeout':
                config[key] = 10
            elif isinstance(config[key], bool):
                config[key] = True
            else:
                config[key] = None

        await self.middleware.call('datastore.update', 'directoryservices', pk, config)

    @api_method(
        DirectoryServicesLeaveArgs, DirectoryServicesLeaveResult,
        roles=['DIRECTORY_SERVICE_WRITE'],
        audit='Leaving directory services domain'
    )
    @job(lock='directoryservices_change')
    def leave(self, job, cred):
        """ Leave an Active Directory or IPA domain. Calling this endpoint when the directory services status is
        `HEALTHY` will cause TrueNAS to remove its account from the domain and then reset the local directory
        services configuration on TrueNAS. """
        revert = []
        verrors = ValidationErrors()

        ds_config = self.middleware.call_sync('directoryservices.config')
        if not ds_config['enable']:
            raise CallError(
                'The directory service must be enabled and healthy before the TrueNAS server can leave the domain.'
            )

        # overwrite cred with admin-provided one. We need elevated permissions to do this
        ds_config['credential'] = cred['credential']

        ds_type = DSType(ds_config['service_type'])
        if ds_type not in (DSType.IPA, DSType.AD):
            raise CallError(f'{ds_type}: Directory service type does not support leave operations')

        # Set our directory services health state to LEAVING so that automatic health checks are disabled
        # and we don't try to recover while leaving the domain.
        self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.LEAVING.name)
        validate_credential('directoryservices.leave_domain', ds_config, verrors, revert)
        if verrors:
            self.__revert_changes(revert)

        verrors.check()

        # We've successfully managed to kinit for domain with hopefully an admin credential
        try:
            job.wrap_sync(self.middleware.call_sync('directoryservices.connection.leave_domain'))
        except Exception:
            # Make sure we nuke our kerberos ticket
            self.logger.warning('Failed to cleanly leave domain', exc_info=True)
            self.__revert_changes(revert)
            raise

        self.middleware.call_sync('directoryservices.health.set_state', ds_type.value, DSStatus.DISABLED.name)
        job.set_progress(description='Restarting services')
        self.middleware.call_sync('kerberos.stop')

        for etc_file in ds_type.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

        # These service changes need to be propagated to the remote node since join will cease working
        if ds_type is DSType.IPA:
            self.middleware.call_sync('service.control', 'STOP', 'sssd').wait_sync(raise_error=True)
        else:
            # Clearing the idmap cache also restarts winbindd
            self.middleware.call_sync('idmap.clear_idmap_cache').wait(raise_error=True)

        self.middleware.call_sync('directoryservices.restart_dependent_services')
        job.set_progress(description=f'Successfully left {ds_config["configuration"]["domain"]}')

    @api_method(
        DirectoryServicesCertificateChoicesArgs, DirectoryServicesCertificateChoicesResult,
        roles=['DIRECTORY_SERVICE_READ']
    )
    async def certificate_choices(self):
        """ Available certificate choices for use with the `LDAP_MTLS` `credential_type`.
        Note that prior configuration of LDAP server is required and uploading a custom
        certificate to TrueNAS may also be required. """
        return {
            i['id']: i['name']
            for i in await self.middleware.call(
                'certificate.query', [
                    ['cert_type', '=', 'CERTIFICATE'],
                    ['cert_type_CSR', '=', False],
                    ['cert_type_CA', '=', False]
                ]
            )
        }
