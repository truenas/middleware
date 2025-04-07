from middlewared.service import job, Service
from middlewared.service_exception import CallError
from middlewared.api import api_method
from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, NonEmptyString, single_argument_args,
    ForUpdateMetaclass,
)
from pydantic import Secret


class LegacyADEntry(BaseModel):
    """ Temporary shim to keep private API alive for UI migration """
    id: int
    domainname: str
    bindname: str
    bindpw: Secret[str]
    verbose_logging: bool
    use_default_domain: bool
    allow_trusted_doms: bool
    allow_dns_updates: bool
    disable_freenas_cache: bool
    restrict_pam: bool
    kerberos_realm: int | None
    kerberos_principal: str | None
    site: str | None
    timeout: int
    dns_timeout: int
    nss_info: NonEmptyString | None
    createcomputer: str | None
    netbiosname: NonEmptyString
    netbiosalias: list[NonEmptyString]
    enable: bool


class LegacyADNoArgs(BaseModel):
    pass


class LegacyADConfigResult(BaseModel):
    result: LegacyADEntry


@single_argument_args("activedirectory_update")
class LegacyADUpdateArgs(LegacyADEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class LegacyADUpdateResult(BaseModel):
    result: LegacyADEntry


@single_argument_args('credential')
class LegacyADLeaveArgs(BaseModel):
    username: NonEmptyString
    password: Secret[NonEmptyString]


class LegacyADLeaveResult(BaseModel):
    result: None


class LegacyADNSSChoicesResult(BaseModel):
    result: list


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"
        private = True

    @api_method(LegacyADNoArgs, LegacyADNSSChoicesResult, private=True)
    async def nss_info_choices(self):
        """
        Returns list of available LDAP schema choices.
        """
        return await self.middleware.call('directoryservices.nss_info_choices', 'ACTIVEDIRECTORY')

    async def dsconfig_to_adconfig(self, data):
        smb = await self.middleware.call('smb.config')

        out = {
            'id': data['id'],
            'domainname': '',
            'bindname': '',
            'bindpw': '',
            'verbose_logging': False,
            'use_default_domain': False,
            'allow_trusted_doms': False,
            'disable_freenas_cache': not data['enable_account_cache'],
            'restrict_pam': False,
            'kerberos_realm': None,
            'kerberos_principal': '',
            'allow_dns_updates': False,
            'site': None,
            'timeout': 10,
            'dns_timeout': data['timeout'],
            'nss_info': 'TEMPLATE',
            'createcomputer': None,
            'netbiosname': smb['netbiosname'],
            'netbiosalias': smb['netbiosalias'],
            'enable': data['enable']
        }

        if data['service_type'] != 'ACTIVEDIRECTORY':
            return out

        if data['kerberos_realm']:
            realm_id = (await self.middleware.call('kerberos.realm.query', [
                ['realm', '=', data['kerberos_realm']],
            ], {'get': True}))['id']
            out['kerberos_realm'] = realm_id

        if data['credential']['credential_type'] == 'KERBEROS_PRINCIPAL':
            out['kerberos_principal'] = data['credential']['principal']

        out['createcomputer'] = data['configuration']['computer_account_ou']
        out['use_default_domain'] = data['configuration']['use_default_domain']
        out['allow_trusted_doms'] = data['configuration']['enable_trusted_domains']
        out['allow_dns_updates'] = data['enable_dns_updates']
        out['site'] = data['configuration']['site']
        out['domainname'] = data['configuration']['domain']
        return out

    async def adconfig_to_dsconfig(self, data):
        dsconfig = await self.middleware.call('directoryservices.config')
        if dsconfig['service_type'] not in (None, 'ACTIVEDIRECTORY'):
            raise CallError(
                'Active directory configuration may not be changed while a differentdirectory service is configured'
            )

        if not data.get('domainname'):
            raise CallError('domainname is required')

        if data.get('enable_trusted_doms'):
            raise CallError('Trusted domains may not be enabled throuh legacy interface')

        out = {
            'enable': data['enable'],
            'service_type': 'ACTIVEDIRECTORY',
            'credential': dsconfig['credential'],
            'enable_account_cache': not data.get('disable_freenas_cache', False),
            'enable_dns_updates': data.get('allow_dns_updates', True),
            'timeout': data.get('timeout', 10),
            'kerberos_realm': dsconfig['kerberos_realm'],
            'configuration': None,
        }

        if data.get('kerberos_principal'):
            out['credential'] = {
                'credential_type': 'KERBEROS_PRINCIPAL',
                'kerberos_principal': data['kerberos_principal']
            }
        elif data.get('bindpw'):
            out['credential'] = {
                'credential_type': 'KERBEROS_USER',
                'username': data['bindname'],
                'password': data['bindpw']
            }

        if data.get('kerberos_realm'):
            r = await self.middleware.call('kerberos.realm.get_instance', data['kerberos_realm'])
            out['kerberos_realm'] = r['realm']

        hostname = data.get('netbiosname')
        if not hostname and dsconfig['service_type'] == 'ACTIVEDIRECTORY':
            # keep existing hostname
            hostname = dsconfig['configuration']['hostname']

        out['configuration'] = {
            'hostname': hostname,
            'domain': data['domainname'],
            'enable_trusted_domains': False,
            'trusted_domains': [],
            'use_default_domain': data.get('use_default_domain', False),
            'computer_account_ou': data.get('createcomputer'),
            'site': data.get('site'),
        }

        if dsconfig['service_type'] == 'ACTIVEDIRECTORY':
            out['configuration']['idmap'] = dsconfig['configuration']['idmap']

        return out

    @api_method(LegacyADNoArgs, LegacyADConfigResult, private=True)
    async def config(self):
        ds_config = await self.middleware.call('directoryservices.config')
        return await self.dsconfig_to_adconfig(ds_config)

    @api_method(
        LegacyADUpdateArgs, LegacyADUpdateResult,
        audit='Activedirectory Update',
        private=True
    )
    @job(lock="AD_start_stop")
    async def update(self, job, data):
        self.logger.warning("Directory services were updated through the legacy API wrapper.")

        ds_config = await self.adconfig_to_dsconfig(data)

        update_job = await self.middleware.call('directoryservices.update', ds_config)
        result = await job.wrap(update_job)
        return await self.dsconfig_to_adconfig(result)

    @api_method(
        LegacyADLeaveArgs, LegacyADLeaveResult,
        audit='Activedirectory Leave',
        private=True,
    )
    @job(lock="AD_start_stop")
    async def leave(self, job, data):
        self.logger.warning("Active directory leave through legacy API wrapper.")
        leave_job = await self.middleware.call('directoryservices.leave', {'credential': {'credential_type': 'KERBEROS_USER', **data}})
        await job.wrap(leave_job)
