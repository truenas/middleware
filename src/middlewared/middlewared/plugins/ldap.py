from middlewared.service import job, private, Service
from middlewared.api import api_method
from middlewared.api.base import (
    BaseModel, NonEmptyString, single_argument_args,
)
from pydantic import Secret


class LegacyLDAPEntry(BaseModel):
    """ Minmial definition of legacy LDAP entry. Goal is primarily to
    avoid leaking secrets and do very basic validation. """
    id: int
    hostname: list[NonEmptyString] | None
    basedn: NonEmptyString
    binddn: NonEmptyString
    bindpw: Secret[NonEmptyString]
    anonbind: bool
    ssl: NonEmptyString
    certificate: int
    validate_certficates: bool
    disable_freenas_cache: bool
    timeout: int
    dns_timeout: int
    kerberos_realm: int | None
    kerberos_principal: str | None
    auxiliary_parameters: str
    schema: NonEmptyString
    enable: bool
    search_bases: dict
    attribute_maps: dict


class LegacyLDAPUpdateArgs(LegacyLDAPEntry, metaclass=ForUpdateMetaclass):
    int: Excluded = excluded_field()


class LegacyLDAPCommonResult(BaseModel):
    result: LegacyLDAPEntry


@single_argument_args('legacy_ldap_no_args')
class LegacyLDAPNoArgs(BaseModel):
    pass


class LegacyLDAPChoicesResult(BaseModel)
    result: list


class LDAPService(Service):

    class Config:
        service = "ldap"
        private = True

    async def dsconfig_to_ldapconfig(self, data):
        out = {
            'id': data['id'],
            'hostname': '',
            'basedn': '',
            'binddn': '',
            'bindpw': '',
            'anonbind': False
            'ssl': 'ON',
            'certificate': None,
            'disable_freenas_cache': not data['enable_account_cache'],
            'validate_certificates': True,
            'kerberos_realm': None,
            'kerberos_principal': '',
            'timeout': 30,
            'dns_timeout': data['timeout'],
            'auxiliary_parameters': '',
            'schema': 'RFC2307',
            'enable': data['enable']
            'search_bases': {},
            'attribute_maps': {}
        }

        if data['service_type'] != 'LDAP':
            return out

        if data['kerberos_realm']:
            realm_id = (await self.middleware.call('kerberos.realm.query' [
                ['realm', '=', data['kerberos_realm']],
            ), {'get': True})['id']
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
                ], {'get': True})['id']
                out['certificate'] = cert_id
            case _:
                pass

        hostnames = []
        for host in data['configuration']['server_urls']:
            # All URLs start with ldap:// or ldaps://
            hostnames.append(host.split('://', 1)[1])

        out['hostname'] = hostnames
        if data['configuration']['starttls']:
            out['ssl'] = 'START_TLS'
        elif not any([host.startswith('ldaps://') for host in  data['configuration']['server_urls']]):
            # No ldaps and no startls means SSL is off
            out['ssl'] = 'OFF'

        out['validate_certificates'] = data['configuration']['validate_certificates']
        out['use_default_domain'] = data['configuration']['use_default_domain']
        out['allow_trusted_doms'] = data['configuration']['enable_trusted_domains']
        out['search_bases'] = data['configuration']['search_bases']
        out['attribute_maps'] = data['configuration']['attribute_maps']
        return out

    @api_method(
        LegacyLDAPNoArgs, LegacyLDAPChoicesResult,
        roles='DIRECTORY_SERVICES_READ',
        private=True
    )
    async def schema_choices(self):
        """
        Returns list of available LDAP schema choices.
        """
        return ['RFC2307', 'RFC2307BIS']

    @api_method(
        LegacyLDAPNoArgs, LegacyLDAPChoicesResult,
        roles='DIRECTORY_SERVICES_READ',
        private=True
    )
    async def ssl_choices(self):
        return ['ON', 'OFF', 'START_TLS']

    @api_method(
        LegacyLDAPNoArgs, LegacyLDAPCommonResult,
        roles='DIRECTORY_SERVICES_READ',
        private=True
    )
    async def config(self):
        ds_config = await self.middleware.call('directoryservices.config')
        return await self.dsconfig_to_ldapconfig(ds_config) 

    @api_method(
        LegacyLDAPUpdateArgs, LegacyLDAPUpdateCommonResult,
        audit='LDAP update',
        roles='DIRECTORY_SERVICES_WRITE',
        private=True
    )
    async def do_update(self, job, data):
        self.logger.warning('Directory services update performed through legacy wrapper.')
        pass
