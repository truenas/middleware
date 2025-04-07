from middlewared.service import job, private, Service
from middlewared.api import api_method
from middlewared.api.base import (
    BaseModel, NonEmptyString, single_argument_args,
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
    createcomputer: str
    netbiosname: NonEmptyString 
    netbiosalias: list[NonEmptyString]
    enable: bool


class LegacyADNoArgs(BaseModel):
    pass

class LegacyADConfigResult(BaseModel):
    result: LegacyADEntry

class LegacyADUpdateArgs(LegacyADEntry, metaclass=ForUpdateMetaClass):
    id: Excluded = excluded_field()


class LegacyADNSSInfoChoicesArg(B


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

    @api_method(LegacyADNoArgs, LegacyADNSSChoicesResult, roles=['DIRECTORY_SERVICE_READ'], private=True)
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
            'timeout': 60,
            'dns_timeout': data['timeout'],
            'nss_info': 'TEMPLATE',
            'createcomputer': '',
            'netbiosname': smb['netbiosname'],
            'netbiosalias': smb['netbiosalias'],
            'enable': data['enable'] 
        }

        if data['service_type'] != 'ACTIVEDIRECTORY':
            return out

        if data['kerberos_realm']:
            realm_id = (await self.middleware.call('kerberos.realm.query' [
                ['realm', '=', data['kerberos_realm']],
            )), {'get': True})['id']
            out['kerberos_realm'] = realm_id

        if data['credential']['credential_type'] == 'KERBEROS_PRINCIPAL':
            out['kerberos_principal'] = data['credential']['kerberos_principal']

        out['createcomputer'] = data['configuration']['computer_account_ou']
        out['use_default_domain'] = data['configuration']['use_default_domain']
        out['allow_trusted_doms'] = data['configuration']['enable_trusted_domains']
        out['allow_dns_updates'] = data['configuration']['enable_dns_updates']
        out['site'] = data['configuration']['site']
        out['domainname'] = data['configuration']['domain']
        return out

    async def adconfig_to_dsconfig(self, data):
        dsconfig = await self.middleware.call('directoryservices.config')
        out = {
            'enable': data['enable'],
            'service_type': 'ACTIVEDIRECTORY',
            'credential': None,
            'enable_account_cache': not data['disable_freenas_cache'],
            'enable_dns_updates': data['allow_dns_updates'],
            'timeout': data['dns_timeout'],
            'kerberos_realm': None,
            'configuration': None,
        }

        if data['kerberos_principal']:
            out['credential'] = {
                'credential_type': 'KERBEROS_PRINCIPAL',
                'kerberos_principal': data['kerberos_principal']
            }
        elif data['bindpw']:
            out['credential'] = {
                'credential_type': 'KERBEROS_USER',
                'username': data['bindname'],
                'password': data['bindpw']
            }

        out['configuration'] = {
            'hostname': data['netbiosname'],
            'domain': data['domainname'],
            'enable_trusted_domains': data['allow_trusted_doms'],
            'trusted_domains': None,
            'use_default_domain': data['use_default_domain'],
            'computer_account_ou': data['computer_account_ou'],
            'site': data['site'],
            'idmap': None,
        }

        if dsconfig['service_type'] == 'ACTIVEDIRECTORY':
            out['configuration']['idmap'] = dsconfig['configuration']['idmap']
            out['configuration']['trusted_domains'] = dsconfig['configuration']['trusted_domains']

        return out

    @api_method(LegacyADNoArgs, LegacyADConfigResult, roles=['DIRECTORY_SERVICES_READ'], private=True)
    async def config(self):
        ds_config = await self.middleware.call('directoryservices.config')
        return await self.dsconfig_to_adconfig(ds_config)


    @api_method(
        LegacyADUpdateArgs, LegacyADUpdateResult,
        audit='Activedirectory Update',
        roles=['DIRECTORY_SERVICES_WRITE'],
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
        roles=['DIRECTORY_SERVICES_WRITE'],
        audit='Leave Active directory domain',
        private=True,
    )
    @job(lock="AD_start_stop")
    async def leave(self, job, data):
        self.logger.warning("Active directory leave through legacy API wrapper.")
        leave_job = await self.middleware.call('directoryservices.leave', {'credential_type': 'KERBEROS_USER', **data})
        await job.wrap(leave_job)
        
