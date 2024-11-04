from middlewared.service import job, Service
from middlewared.utils.directoryservices.constants import DSCredentialType, DSType


NULL_LDAP_CONFIG = {
    'hostname': [],
    'basedn': '',
    'binddn': '',
    'bindpw': '',
    'anonbind': False,
    'ssl': 'ON',
    'timeout': 60,
    'dns_timeout': 10,
    'auxiliary_parameters': '',
    'schema': 'RFC2307',
    'enable': False,
    'certificate': None,
    'kerberos_realm': None,
    'kerberos_principal': '',
    'validate_certificates': True,
    'disable_freenas_cache': False,
    'server_type': None,
}


class LDAPService(Service):

    class Config:
        service = "ldap"
        private = True

    async def convert_to_dsconfig(self, data):
        out = {
            'dstype': DSType.IPA if data['server_type'] == 'FREEIPA' else DSType.LDAP,
            'enable': data['enable'],
            'enable_cache': not data['disable_freenas_cache'],
            'configuration': None,
            'timeout': {
                'service': data['timeout'],
                'dns': data['dns_timeout'],
            },
        }

        out['configuration'] = {
            'basedn': data['basedn'],
            'credential': None,
            'ssl_config': {
                'ssl': None,
                'validate_certificates': data['validate_certificates']
            },
        }

        match data['server_type']:
            case 'FREEIPA':
                out['configuration'].update({
                    'domainname': data['domainname'],  # fixme convert from basedn
                    'target_server': data['hostname'][0] if data['hostname'] else [],
                    'allow_dns_updates': True,
                })
            case 'OPENLDAP' | None:
                out['configuration'].update({
                    'server_hostnames': data['hostname'],
                    'nss_info': data['schema'],
                })

        if data['kerberos_principal']:
            out['configuration']['credential'] = {
                'credential_type': DSCredentialType.KERBEROS_PRINCIPAL,
                'kerberos_principal': data['kerberos_principal']
            }
        elif data['binddn']:
            if data['server_type'] == 'FREEIPA':
                dn = data['binddn'].split(',')
                username = dn[0].split('=')[1].strip()

                out['configuration']['credential'] = {
                    'credential_type': DSCredentialType.USERNAME_PASSWORD,
                    'binddn': username,
                    'bindpw': data['bindpw']
                }
            else:
                out['configuration']['credential'] = {
                    'credential_type': DSCredentialType.LDAPDN_PASSWORD,
                    'binddn': data['binddn'],
                    'bindpw': data['bindpw']
                }

        elif data['certificate']:
            pass  # FIXME

        realm = await self.middleware.call('kerberos.realm.query', [['id', '=', data['kerberos_realm']]])
        if realm:
            out['configuration']['kerberos_realm'] = realm[0]['id']

        return out

    async def config(self):
        config = await self.middleware.call('directoryservices.config')
        dsconfig = config['configuration']
        out = NULL_LDAP_CONFIG.copy() | {
            'basedn': dsconfig['basedn'],
            'timeout': config['timeout']['service'],
            'dns_timeout': config['timeout']['dns'],
            'validate_certificates': dsconfig['ssl_config']['validate_certificates'],
            'nss_info': dsconfig['nss_info'],
        }

        if not config['dstype'] in (DSType.IPA, DSType.LDAP):
            return out

        match config['dstype']:
            case DSType.LDAP:
                out.update({
                    'hostname': dsconfig['server_hostnames'],
                    'auxiliary_parameters': dsconfig['auxiliary_parameters'],
                    'server_type': 'OPENLDAP',
                })
            case DSType.IPA:
                out.update({
                    'hostname': [dsconfig['target_server']],
                    'server_type': 'FREEIPA',
                })

        match dsconfig['credential']['credential_type']:
            case DSCredentialType.LDAPDN_PASSWORD:
                out['binddn'] = dsconfig['credential']['binddn']
                out['bindpw'] = dsconfig['credential']['bindpw']
            case DSCredentialType.KERBEROS_PRINCIPAL:
                out['kerberos_principal'] = dsconfig['credential']['kerberos_principal']
            case DSCredentialType.ANONYMOUS:
                out['anonbind'] = True
            case DSCredentialType.CERTIFICATE:
                # FIXME
                pass

        realm = await self.middleware.call('kerberos.realm.query', [['id', '=', dsconfig['kerberos_realm']]])
        if realm:
            out['configuration']['kerberos_realm'] = realm[0]['realm']

        return out

    @job()
    async def update(self, job, data):
        # This is a wrapper around directoryservices.config / directoryservices.update
        # to maintain private api compatibility while consumers are converting for FT.
        config = await self.config()
        payload = await self.convert_to_dsconfig(config)

        dsjob = await self.middleware.call('directoryservices.update', payload)
        await job.wrap(dsjob)
        return await self.config()
