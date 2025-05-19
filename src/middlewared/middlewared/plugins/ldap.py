from middlewared.service import job, Service
from middlewared.api import api_method
from middlewared.api.base import (
    BaseModel, NonEmptyString, single_argument_args,
    Excluded, excluded_field, ForUpdateMetaclass,
)
from pydantic import Field, Secret


class LegacyLDAPEntry(BaseModel):
    """ Minmial definition of legacy LDAP entry. Goal is primarily to
    avoid leaking secrets and do very basic validation. """
    id: int
    hostname: list
    basedn: str
    binddn: str
    bindpw: Secret[str]
    anonbind: bool
    ssl: NonEmptyString
    certificate: int | None
    validate_certificates: bool
    disable_freenas_cache: bool
    timeout: int
    dns_timeout: int
    kerberos_realm: int | None
    kerberos_principal: str | None
    auxiliary_parameters: str
    enable: bool
    search_bases: dict
    attribute_maps: dict
    ldap_schema: NonEmptyString = Field(alias='schema')
    cert_name: str | None
    uri_list: list
    server_type: str | None
    has_samba_schema: bool


@single_argument_args("ldap_update")
class LegacyLDAPUpdateArgs(LegacyLDAPEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    cert_name: Excluded = excluded_field()
    uri_list: Excluded = excluded_field()
    server_type: Excluded = excluded_field()


class LegacyLDAPCommonResult(BaseModel):
    result: LegacyLDAPEntry


class LegacyLDAPNoArgs(BaseModel):
    pass


class LegacyLDAPChoicesResult(BaseModel):
    result: list


class LDAPService(Service):

    class Config:
        service = "ldap"
        private = True

    async def dsconfig_to_ldapconfig(self, data):
        out = {
            'id': data['id'],
            'hostname': [],
            'basedn': '',
            'binddn': '',
            'bindpw': '',
            'anonbind': False,
            'ssl': 'ON',
            'certificate': None,
            'cert_name': None,
            'disable_freenas_cache': not data['enable_account_cache'],
            'validate_certificates': True,
            'kerberos_realm': None,
            'kerberos_principal': '',
            'timeout': 30,
            'dns_timeout': data['timeout'],
            'auxiliary_parameters': '',
            'schema': 'RFC2307',
            'has_samba_schema': False,
            'uri_list': [],
            'server_type': 'OPENLDAP',
            'enable': data['enable'],
            'search_bases': {},
            'attribute_maps': {}
        }

        if data['service_type'] != 'LDAP':
            return out

        if data['kerberos_realm']:
            realm_id = (await self.middleware.call('kerberos.realm.query' [
                ['realm', '=', data['kerberos_realm']],
            ], {'get': True}))['id']
            out['kerberos_realm'] = realm_id

        match data['credential']['credential_type']:
            case 'KERBEROS_PRINCIPAL':
                out['kerberos_principal'] = data['credential']['kerberos_principal']
            case 'KERBEROS_USER':
                out['binddn'] = data['credential']['username']
                out['bindpw'] = data['credential']['password']
            case 'LDAP_PLAIN':
                out['binddn'] = data['credential']['binddn']
                out['bindpw'] = data['credential']['bindpw']
            case 'LDAP_ANONYMOUS':
                out['anonbind'] = True
            case 'LDAP_MTLS':
                cert_id = (await self.middleware.call('certificate.query', [
                    ['cert_name', '=', data['credential']['client_certificate']]
                ], {'get': True}))['id']
                out['certificate'] = cert_id
                out['cert_name'] = data['credential']['client_certificate']
            case _:
                pass

        hostnames = []
        for host in data['server_urls']:
            # All URLs start with ldap:// or ldaps://
            hostnames.append(host.split('://', 1)[1])

        out['hostname'] = hostnames
        out['uri_list'] = data['server_urls']
        if data['starttls']:
            out['ssl'] = 'START_TLS'
        elif not any([host.startswith('ldaps://') for host in data['server_urls']]):
            # No ldaps and no startls means SSL is off
            out['ssl'] = 'OFF'

        out['validate_certificates'] = data['validate_certificates']
        out['search_bases'] = data['search_bases']
        out['attribute_maps'] = data['attribute_maps']
        out['basedn'] = data['basedn']
        return out

    async def ldapconfig_to_dsconfig(self, data):
        out = {
            'enable': data['enable'],
            'service_type': 'LDAP',
            'credential': None,
            'enable_account_cache': not data['disable_freenas_cache'],
            'enable_dns_updates': False,
            'timeout': data['dns_timeout'],
            'kerberos_realm': None,
        }

        if data['kerberos_principal']:
            out['credential'] = {
                'credential_type': 'KERBEROS_PRINCIPAL',
                'kerberos_principal': data['kerberos_principal']
            }
        elif data['kerberos_realm']:
            out['credential'] = {
                'credential_type': 'KERBEROS_USER',
                'username': data['binddn'],
                'password': data['bindpw']
            }
        elif data['anonbind']:
            out['credential'] = {'credential_type': 'LDAP_ANONYMOUS'}
        elif data['certificate']:
            cert_name = (await self.middleware.call('certificate.get_instance', data['certificate']))['cert_name']
            out['credential'] = {
                'credential_type': 'LDAP_MTLS',
                'certificate': cert_name,
            }
        else:
            out['credential'] = {
                'credential_type': 'LDAP_PLAIN',
                'binddn': data['binddn'],
                'bindpw': data['bindpw']
            }

        if out['credential']['credential_type'].startswith('KERBEROS') and data['kerberos_realm']:
            out['kerberos_realm'] = (await self.middleware.call('kerberos.realm.get_instance', data['kerberos_realm']))['id']

        starttls = data['ssl'] == 'START_TLS'
        prefix = 'ldaps://' if data['ssl'] == 'ON' else 'ldap://'
        server_urls = [f'{prefix}{srv}' for srv in data['hostname']]

        out.update({
            'server_urls': server_urls,
            'starttls': starttls,
            'basedn': data['basedn'],
            'validate_certificates': data['validate_certificates'],
            'schema': data['schema'],
            'auxiliary_parameters': data['auxiliary_parameters'],
        })

        return out

    @api_method(
        LegacyLDAPNoArgs, LegacyLDAPChoicesResult,
        private=True
    )
    async def schema_choices(self):
        """
        Returns list of available LDAP schema choices.
        """
        return ['RFC2307', 'RFC2307BIS']

    @api_method(
        LegacyLDAPNoArgs, LegacyLDAPChoicesResult,
        private=True
    )
    async def ssl_choices(self):
        return ['ON', 'OFF', 'START_TLS']

    @api_method(
        LegacyLDAPNoArgs, LegacyLDAPCommonResult,
        private=True
    )
    async def config(self):
        ds_config = await self.middleware.call('directoryservices.config')
        return await self.dsconfig_to_ldapconfig(ds_config)

    @api_method(
        LegacyLDAPUpdateArgs, LegacyLDAPCommonResult,
        audit='LDAP update',
        private=True
    )
    @job()
    async def update(self, job, data):
        self.logger.warning('Directory services update performed through legacy wrapper.')
        ds_config = await self.ldapconfig_to_dsconfig(data)
        update_job = await self.middleware.call('directoryservices.update', ds_config)
        result = await job.wrap(update_job)
        return await self.dsconfig_to_ldapconfig(result)
