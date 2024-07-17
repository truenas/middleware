from middlewared.schema import accepts, Int, List, Ref, returns
from middlewared.service import Service


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @accepts()
    @returns(List(items=[Ref('certificate_entry')]))
    async def certificate_choices(self):
        """
        Returns certificates which can be used by applications.
        """
        return await self.middleware.call(
            'certificate.query', [['revoked', '=', False], ['cert_type_CSR', '=', False], ['parsed', '=', True]],
            {'select': ['name', 'id']}
        )

    @accepts()
    @returns(List(items=[Ref('certificateauthority_entry')]))
    async def certificate_authority_choices(self):
        """
        Returns certificate authorities which can be used by applications.
        """
        return await self.middleware.call(
            'certificateauthority.query', [['revoked', '=', False], ['parsed', '=', True]], {'select': ['name', 'id']}
        )

    @accepts()
    @returns(List(items=[Int('used_port')]))
    async def used_ports(self):
        """
        Returns ports in use by applications.
        """
        return sorted(list(set({
            host_port['host_port']
            for app in await self.middleware.call('app.query')
            for port_entry in app['active_workloads']['used_ports']
            for host_port in port_entry['host_ports']
        })))
