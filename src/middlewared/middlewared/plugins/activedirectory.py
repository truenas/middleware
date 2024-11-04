from middlewared.utils.directoryservices.constants import DSType, DSCredentialType
from middlewared.service import job, Service


NULL_AD_CONFIG = {
    'domainname': '',
    'bindname': '',
    'bindpw': '',
    'verbose_logging': False,
    'use_default_domain': False,
    'allow_trusted_domains': False,
    'disable_freenas_cache': False,
    'restrict_pam': False,
    'site': None,
    'kerberos_realm': None,
    'kerberos_principal': None,
    'timeout': 60,
    'dns_timeout': 10,
    'nss_info': 'TEMPLATE',
    'create_computer': '',
    'netbiosname': '',
    'netbiosalias': [],
    'enable': False
}


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"
        private = True

    async def config(self):
        config = await self.middleware.call('directoryservices.config')
        adconfig = config['configuration']
        smb = await self.middleware.call('smb.config')
        netbios_info = {'netbiosname': smb['netbiosname'], 'netbiosalias': smb['netbiosalias']}
        out = NULL_AD_CONFIG.copy() | netbios_info

        if config['dstype'] != DSType.AD:
            return out

        out.update({
            'domainname': adconfig['domainname'],
            'use_default_domain': adconfig['use_default_domain'],
            'allow_trusted_doms': adconfig['allow_trusted_domains'],
            'allow_dns_updates': adconfig['allow_dns_updates'],
            'disable_freenas_cache': not adconfig['enable_cache'],
            'timeout': config['timeout']['service'],
            'dns_timeout': config['timeout']['dns'],
            'nss_info': adconfig['nss_info'],
            'createcomputer': adconfig['computer_account_ou'],
            'site': adconfig['site'],
        })

        realm = await self.middleware.call('kerberos.realm.query', [['realm', 'C=', adconfig['kerberos_realm']]])
        if realm:
            out['kerberos_realm'] = realm[0]['id']

        match adconfig['credential']['credential_type']:
            case DSCredentialType.KERBEROS_PRINCIPAL:
                out['kerberos_principal'] = adconfig['credential']['kerberos_principal']
            case DSCredentialType.USERNAME_PASSWORD:
                out['bindname'] = adconfig['credential']['bindname']

        return out

    async def convert_to_dsconfig(self, data):
        out = {
            'dstype': DSType.AD,
            'enable': data['enable'],
            'enable_cache': not data['disable_freenas_cache'],
            'configuration': None,
            'timeout': {
                'service': data['timeout'],
                'dns': data['dns_timeout'],
            },
        }
        out['configuration'] = {
            'domainname': data['domainname'],
            'credential': None,
            'computer_account_ou': data['createcomputer'],
            'allow_dns_updates': data['allow_dns_updates'],
            'allow_trusted_domains': data['allow_trusted_domains'],
            'use_default_domain': data['use_default_domain'],
            'nss_info': data['nss_info'],
        }

        if data['kerberos_principal']:
            out['configuration']['credential'] = {
                'credential_type': DSCredentialType.KERBEROS_PRINCIPAL,
                'kerberos_principal': data['kerberos_principal']
            }
        elif data['bindname']:
            out['configuration']['credential'] = {
                'credential_type': DSCredentialType.USERNAME_PASSWORD,
                'bindname': data['bindnname'],
                'bindpw': data['bindpw']
            }

        realm = await self.middleware.call('kerberos.realm.query', [['id', '=', data['kerberos_realm']]])
        if realm:
            out['configuration']['kerberos_realm'] = realm[0]['id']

        return out

    @job()
    async def update(self, job, data):
        config = await self.config() | data
        payload = await self.convert_to_dsconfig(self, config)
        dsjob = await self.middleware.call('directoryservices.update', payload)
        await job.wrap(dsjob)
        return await self.config()
