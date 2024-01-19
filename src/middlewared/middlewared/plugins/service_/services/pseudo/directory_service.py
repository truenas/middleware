from middlewared.plugins.service_.services.base import ServiceInterface, ServiceState
from middlewared.plugins.service_.services.base import systemd_unit


class PseudoServiceBase(ServiceInterface):
    plugin = NotImplemented

    async def get_state(self):
        return ServiceState(
            await self.middleware.call(f"{self.plugin}.started"),
            [],
        )

    async def start(self):
        await self.middleware.call(f"{self.plugin}.start")

    async def stop(self):
        await self.middleware.call(f"{self.plugin}.stop")


class ActiveDirectoryService(PseudoServiceBase):
    name = "activedirectory"

    plugin = "activedirectory"

    restartable = True
    reloadable = True

    async def start(self):
        if not (domain := (await self.middleware.call('activedirectory.config'))['domainname']):
            raise CallError('Active directory service is not configured')

        ad_job = await self.middleware.call('activedirectory.update', {
            'domainname': domain,
            'enable': True
        })

        await ad_job.wait(raise_error=True)

    async def stop(self):
        if not (domain := (await self.middleware.call('activedirectory.config'))['domainname']):
            raise CallError('Active directory service is not configured')

        ad_job = await self.middleware.call('activedirectory.update', {
            'domainname': domain,
            'enable': False
        })

        await ad_job.wait(raise_error=True)

    async def restart(self):
        await self.middleware.call('kerberos.stop')
        await self.middleware.call('kerberos.start')
        await self.middleware.call('service.restart', 'idmap')


    async def reload(self):
        await self.middleware.call('service.reload', 'idmap')


class LdapService(PseudoServiceBase):
    name = "ldap"

    plugin = "ldap"

    async def __compress(self, data):
        data.pop('uri_list')
        data.pop('cert_name')
        data.pop('server_type')

    async def start(self):
        config = await self.middleware.call('ldap.config')
        if not config['hostname']:
            raise CallError('LDAP service is not configured')

        await self.__compress(config)
        ldap_job = await self.middleware.call('ldap.update', config | {
            'enable': True
        })
        await ldap_job.wait(raise_error=True)

    async def stop(self):
        config = await self.middleware.call('ldap.config')
        if not config['hostname']:
            raise CallError('LDAP service is not configured')

        await self.__compress(config)
        ldap_job = await self.middleware.call('ldap.update', config | {
            'enable': False
        })
        await ldap_job.wait(raise_error=True)
