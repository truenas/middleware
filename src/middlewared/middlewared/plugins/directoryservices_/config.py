import middlewared.sqlalchemy as sa

from middlewared.service import Service, private
from middlewared.utils.directoryservices.constants import DSCredentialType, DSLdapSsl, DSType


class DirectoryServicesModel(sa.Model):
    __tablename__ = 'directoryservice_configuration'

    id = sa.Column(sa.Integer(), primary_key=True)
    # Common options for all directory services
    common_enable = sa.Column(sa.Boolean())
    common_enable_cache = sa.Column(sa.Boolean(), default=True)
    common_type = sa.Column(sa.String(120))
    common_service_timeout = sa.Column(sa.Integer(), default=45)
    common_dns_timeout = sa.Column(sa.Integer(), default=10)
    common_bindname = sa.Column(sa.String(120), nullable=True)
    common_allow_dns_updates = sa.Column(sa.Boolean())
    common_nss_info = sa.Column(sa.String(120), nullable=True)
    common_kerberos_realm_id = sa.Column(
        sa.ForeignKey('directoryservice_kerberosrealm.id', ondelete='SET NULL'),
        index=True, nullable=True
    )
    common_kerberos_principal = sa.Column(sa.String(255), nullable=True)
    common_ssl = sa.Column(sa.String(120), default=DSLdapSsl.LDAPS)
    common_validate_certificates = sa.Column(sa.Boolean(), default=True)

    # AD-specific options
    ad_domainname = sa.Column(sa.String(120))
    ad_allow_trusted_doms = sa.Column(sa.Boolean(), default=False)
    ad_use_default_domain = sa.Column(sa.Boolean(), default=False)
    ad_site = sa.Column(sa.String(120), nullable=True)
    ad_computer_ou = sa.Column(sa.String(255))

    # IPA-specific options
    ipa_domainname = sa.Column(sa.String(120))
    ipa_netbios_domainname = sa.Column(sa.String(120))
    ipa_basedn = sa.Column(sa.String(120), nullable=True)
    ipa_domain_sid = sa.Column(sa.String(120), nullable=True)
    ipa_target_server = sa.Column(sa.String(120), nullable=True)

    # LDAP-specific options
    ldap_hostnames = sa.Column(sa.String(120))
    ldap_basedn = sa.Column(sa.String(120), nullable=True)
    ldap_binddn = sa.Column(sa.String(256), nullable=True)
    ldap_bindpw = sa.Column(sa.EncryptedText(), nullable=True)
    ldap_anonbind = sa.Column(sa.Boolean(), default=False)
    ldap_auxiliary_parameters = sa.Column(sa.Text())
    ldap_certificate_id = sa.Column(
        sa.ForeignKey('system_certificate.id'),
        index=True, nullable=True
    )
    # LDAP seach bases
    ldap_base_user = sa.Column(sa.String(256), nullable=True)
    ldap_base_group = sa.Column(sa.String(256), nullable=True)
    ldap_base_netgroup = sa.Column(sa.String(256), nullable=True)

    # LDAP attribute maps
    ldap_user_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_user_name = sa.Column(sa.String(256), nullable=True)
    ldap_user_uid = sa.Column(sa.String(256), nullable=True)
    ldap_user_gid = sa.Column(sa.String(256), nullable=True)
    ldap_user_gecos = sa.Column(sa.String(256), nullable=True)
    ldap_user_home_directory = sa.Column(sa.String(256), nullable=True)
    ldap_user_shell = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_last_change = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_min = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_max = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_warning = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_inactive = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_expire = sa.Column(sa.String(256), nullable=True)
    ldap_group_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_group_gid = sa.Column(sa.String(256), nullable=True)
    ldap_group_member = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_member = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_triple = sa.Column(sa.String(256), nullable=True)


def _null_ds_config() -> dict:
    tbl = DirectoryServicesModel.metadata.tables.get('directoryservice_configuration')
    config = {}

    for key, column in tbl.columns.items():
        if key == 'id':
            continue

        if column.default:
            config[key] = column.default

        if column.nullable:
            config[key] = column.default

        match column.type:
            case sa.Boolean:
                config[key] = False
            case sa.String:
                config[key] = ''
            case _:
                raise ValueError(f'{column.type}: unexpected column type')

    return config


NULL_DS_CONFIG = _null_ds_config()


def extend_kerberos_realm(data: dict) -> str:
    if data['kerberos_realm'] is None:
        return None

    return data['kerberos_realm']['krb_realm']


def extend_ssl_config(data: dict) -> dict:
    return {
        'ssl': data['common_ssl'],
        'validate_certificates': data['common_validate_certificates']
    }


def extend_ds_activedirectory(data: dict) -> dict:
    config = {
        'domainname': data['ad_domainname'],
        'credential': None,
        'site': data['ad_site'],
        'kerberos_realm': extend_kerberos_realm(data),
        'computer_account_ou': data['ad_computer_ou'],
        'allow_dns_updates': data['ad_allow_dns_updates'],
        'allow_trusted_domains': data['ad_allow_trusted_domains'],
        'use_default_domain': data['ad_use_default_domain'],
        'nss_info': data['common_nss_info'],
    }

    if data['common_kerberos_principal']:
        config['credential'] = {
            'credential_type': DSCredentialType.KERBEROS_PRINCIPAL,
            'kerberos_princiapl': data['common_kerberos_principal']
        }

    elif data['common_bindname']:
        # For AD we don't store the bindpw ever if we get here it means user
        # perhap removed kerberos principal while DS was disabled.
        config['credential'] = {
            'credential_type': DSCredentialType.USERNAME_PASSWORD,
            'bindname': data['common_bindname'],
            'bindpw': None
        }

    return config


def extend_ds_ipa(data: dict) -> dict:
    config = {
        'domainname': data['ipa_domainname'],
        'netbios_domainname': data['ipa_netbios_domainname'],
        'basedn': data['ipa_basedn'],
        'credential': None,
        'ssl_config': extend_ssl_config(data),
        'kerberos_realm': extend_kerberos_realm(data),
        'domain_sid': data['ipa_domain_sid'],
        'target_server': data['ipa_target_server'],
        'allow_dns_updates': data['ad_allow_dns_updates'],
    }

    if data['common_kerberos_principal']:
        config['credential'] = {
            'credential_type': DSCredentialType.KERBEROS_PRINCIPAL,
            'kerberos_princiapl': data['common_kerberos_principal']
        }

    elif data['common_bindname']:
        config['credential'] = {
            'credential_type': DSCredentialType.USERNAME_PASSWORD,
            'bindname': data['common_bindname'],
            'bindpw': None
        }

    return config


def extend_by_keys_impl(keys: list, data) -> dict:
    return {key: data[f'ldap_{key}'] for key in keys}


def extend_ldap_search_bases(data: dict) -> dict:
    return extend_by_keys_impl(['base_user', 'base_group', 'base_netgroup'], data)


def extend_ldap_passwd_map(data: dict) -> dict:
    return extend_by_keys_impl([
        'user_object_class', 'user_name', 'user_uid', 'user_uid', 'user_gid',
        'user_gecos', 'user_home_directory', 'user_shell',
    ], data)


def extend_ldap_shadow_map(data: dict) -> dict:
    return extend_by_keys_impl([
        'shadow_object_class', 'shadow_last_change', 'shadow_min', 'shadow_max',
        'shadow_warning', 'shadow_inactive', 'shadow_expire',
    ], data)


def extend_ldap_group_map(data: dict) -> dict:
    return extend_by_keys_impl(['group_object_class', 'group_gid', 'group_member'], data)


def extend_ldap_netgroup_map(data: dict) -> dict:
    return extend_by_keys_impl(['netgroup_object_class', 'netgroup_member', 'netgroup_triple'], data)


def extend_ldap_attribute_maps(data: dict) -> dict:
    return {
        'passwd': extend_ldap_passwd_map(data),
        'shadow': extend_ldap_shadow_map(data),
        'group': extend_ldap_group_map(data),
        'netgroup': extend_ldap_netgroup_map(data),
    }


def extend_ds_ldap(data: dict) -> dict:
    return {
        'server_hostnames': data['ldap_hostnames'].split() if data['ldap_hostnames'] else [],
        'credential': None,
        'ssl_config': extend_ssl_config(data),
        'kerberos_realm': extend_kerberos_realm(data),
        'auxiliary_parameters': data['ldap_auxiliary_parameters'],
        'schema': data['common_nss_info'],
        'search_bases': extend_ldap_search_bases(data),
        'attribute_maps': extend_ldap_attribute_maps(data),
    }


def extend_ds_configuration(data: dict) -> dict:
    if data['common_type'] in (None, 'STANDALONE'):
        return None

    match data['common_type']:
        case DSType.AD:
            return extend_ds_activedirectory(data)
        case DSType.IPA:
            return extend_ds_ipa(data)
        case DSType.LDAP:
            return extend_ds_ldap(data)


def compress_standalone(data: dict, compressed: dict) -> dict:
    null_config = NULL_DS_CONFIG.copy()
    return null_config | compressed


def compress_activedirectory(data: dict, compressed: dict) -> dict:
    null_config = NULL_DS_CONFIG.copy()
    dsconfig = data['configuration']

    compressed['ad_domainname'] = dsconfig['domainname']
    compressed['ad_site'] = dsconfig['site']
    compressed['ad_computer_ou'] = dsconfig['computer_account_ou']
    compressed['common_allow_dns_updates'] = dsconfig['allow_dns_updates']
    compressed['ad_allow_trusted_domains'] = dsconfig['allow_trusted_domains']
    compressed['ad_use_default_domain'] = dsconfig['use_default_domain']
    compressed['common_nss_info'] = dsconfig['nss_info']

    dsconfig = data['configuration']

    match dsconfig['credential']['credential_type']:
        case DSCredentialType.KERBEROS_PRINCIPAL:
            compressed['common_kerberos_principal'] = dsconfig['credential']['kerberos_principal']
        case DSCredentialType.USERNAME_PASSWORD:
            compressed['common_bindname'] = dsconfig['credential']['bindname']
            # NOTE: bindpw is never stored in db for AD
        case _:
            # User may be intentionally clearing AD credentials for some reason
            pass

    return null_config | compressed


def compress_ipa(data: dict, compressed: dict) -> dict:
    null_config = NULL_DS_CONFIG.copy()
    dsconfig = data['configuration']

    compressed['ipa_domainname'] = dsconfig['domainname']
    compressed['ipa_netbios_domainname'] = dsconfig['netbios_domainname']
    compressed['ipa_basedn'] = dsconfig['basedn']
    compressed['ipa_domain_sid'] = dsconfig['domain_sid']
    compressed['ipa_target_server'] = dsconfig['target_server']
    compressed['common_allow_dns_updates'] = dsconfig['allow_dns_updates']
    compressed['common_ssl'] = dsconfig['ssl_config']['ssl']
    compressed['common_validate_certificates'] = dsconfig['ssl_config']['validate_certificates']

    match dsconfig['credential']['credential_type']:
        case DSCredentialType.KERBEROS_PRINCIPAL:
            compressed['common_kerberos_principal'] = dsconfig['credential']['kerberos_principal']
        case DSCredentialType.USERNAME_PASSWORD:
            compressed['common_bindname'] = dsconfig['credential']['bindname']
            # NOTE: bindpw is never stored in db for IPA
        case _:
            # User may be intentionally clearing IPA credentials for some reason
            pass

    return null_config | compressed


def compress_ldap_search_bases(data: dict, compressed: dict) -> None:
    for key, value in data['search_bases'].items():
        compressed[f'ldap_{key}'] = value


def compress_ldap_attribute_maps(data: dict, compressed: dict) -> None:
    for key, value in data['attribute_maps'].items():
        compressed[f'ldap_{key}'] = value


def compress_ldap(data: dict, compressed: dict) -> dict:
    null_config = NULL_DS_CONFIG.copy()
    dsconfig = data['configuration']

    compressed['ldap_hostnames'] = ','.join(dsconfig['server_hostnames'])
    compressed['common_ssl'] = dsconfig['ssl_config']['ssl']
    compressed['common_validate_certificates'] = dsconfig['ssl_config']['validate_certificates']
    compressed['ldap_auxiliary_parameters'] = dsconfig['auxiliary_parameters']
    compressed['common_nss_info'] = dsconfig['schema']
    compress_ldap_search_bases(data, compressed)
    compress_ldap_attribute_maps(data, compressed)

    match dsconfig['credential']['credential_type']:
        case DSCredentialType.KERBEROS_PRINCIPAL:
            compressed['common_kerberos_principal'] = dsconfig['credential']['kerberos_principal']
        case DSCredentialType.USERNAME_PASSWORD:
            # Plain auth
            compressed['ldap_binddn'] = dsconfig['credential']['bindname']
            compressed['ldap_bindpw'] = dsconfig['credential']['bindpw']
        case DSCredentialType.ANONYMOUS:
            compressed['ldap_anonbind'] = True
        case DSCredentialType.CERTIFICATE:
            compressed['ldap_certificate_id'] = dsconfig['credential']['certificate_id']
        case _:
            pass

    return null_config | compressed


def compress_ds_configuration(data: dict, compressed: dict) -> dict:
    match data['dstype']:
        case DSType.STANDALONE:
            return compress_standalone(data, compressed)
        case DSType.AD:
            return compress_activedirectory(data, compressed)
        case DSType.IPA:
            return compress_ipa(data, compressed)
        case DSType.LDAP:
            return compress_ldap(data, compressed)
        case _:
            raise ValueError(f'{data["dstype"]}: unknown dstype')


class DirectoryServices(Service):
    class Config:
        service = 'directoryservices'

    @private
    async def extend(self, data: dict) -> dict:
        return {
            'id': data['id'],
            'dstype': data['common_type'],
            'enable': data['common_enable'],
            'enable_cache': data['common_enable_cache'],
            'configuration': extend_ds_configuration(data),
            'timeout': {
                'service': data['common_service_timeout'],
                'dns': data['common_dns_timeout'],
            }
        }

    @private
    async def compress(self, data: dict) -> dict:
        # first start with common configuration
        compressed = {
            # first start with common options
            'common_enable': data['enable'],
            'commmon_enable_cache': data['enable_cache'],
            'commmon_type': data['type'],
            'common_service_timeout': data['timeout']['service'],
            'common_dns_timeout': data['timeout']['dns'],
            'common_kerberos_realm_id': data['configuration']['kerberos_realm_id']
        }

        return compress_ds_configuration(data, compressed)
