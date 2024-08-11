from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import private, Service

from middlewared.utils.gpu import get_nvidia_gpus

from .resources_utils import get_normalized_gpu_choices


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @accepts(
        Str('app_name'),
        Dict(
            'options',
            Bool('alive_only', default=True),
        ),
        roles=['APPS_READ']
    )
    @returns(List(items=[Str('container_id')]))
    async def container_ids(self, app_name, options):
        """
        Returns container IDs for `app_name`.
        """
        return [
            c['id'] for c in (
                await self.middleware.call('app.get_instance', app_name)
            )['active_workloads']['container_details'] if (options['alive_only'] is False or c['state'] == 'running')
        ]

    @accepts(roles=['APPS_READ'])
    @returns(List(items=[Ref('certificate_entry')]))
    async def certificate_choices(self):
        """
        Returns certificates which can be used by applications.
        """
        return await self.middleware.call(
            'certificate.query', [['revoked', '=', False], ['cert_type_CSR', '=', False], ['parsed', '=', True]],
            {'select': ['name', 'id']}
        )

    @accepts(roles=['APPS_READ'])
    @returns(List(items=[Ref('certificateauthority_entry')]))
    async def certificate_authority_choices(self):
        """
        Returns certificate authorities which can be used by applications.
        """
        return await self.middleware.call(
            'certificateauthority.query', [['revoked', '=', False], ['parsed', '=', True]], {'select': ['name', 'id']}
        )

    @accepts(roles=['APPS_READ'])
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

    @accepts(roles=['APPS_READ'])
    @returns(Dict(Str('ip_choice')))
    async def ip_choices(self):
        """
        Returns IP choices which can be used by applications.
        """
        return {
            ip['address']: ip['address']
            for ip in await self.middleware.call('interface.ip_in_use', {'static': True, 'any': True})
        }

    @accepts(roles=['APPS_READ'])
    @returns(Dict('gpu_choices', additional_attrs=True))
    async def gpu_choices(self):
        """
        Returns GPU choices which can be used by applications.
        """
        return {
            gpu['pci_slot']: {
                k: gpu[k] for k in ('vendor', 'description', 'vendor_specific_config', 'pci_slot')
            }
            for gpu in await self.gpu_choices_internal()
            if not gpu['error']
        }

    @private
    async def gpu_choices_internal(self):
        return get_normalized_gpu_choices(
            await self.middleware.call('device.get_gpus'),
            await self.middleware.run_in_thread(get_nvidia_gpus),
        )
