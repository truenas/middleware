from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import private, Service

from middlewared.utils.gpu import get_nvidia_gpus

from .ix_apps.utils import ContainerState
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
    @returns(Dict(
        additional_attrs=True,
        example={
            'afb901dc53a29016c385a9de43f089117e399622c042674f82c10c911848baba': {
                'service_name': 'jellyfin',
                'image': 'jellyfin/jellyfin:10.9.7',
                'state': 'running',
                'id': 'afb901dc53a29016c385a9de43f089117e399622c042674f82c10c911848baba',
            }
        }
    ))
    async def container_ids(self, app_name, options):
        """
        Returns container IDs for `app_name`.
        """
        return {
            c['id']: {
                'service_name': c['service_name'],
                'image': c['image'],
                'state': c['state'],
                'id': c['id'],
            } for c in (
                await self.middleware.call('app.get_instance', app_name)
            )['active_workloads']['container_details'] if (
                options['alive_only'] is False or ContainerState(c['state']) == ContainerState.RUNNING
            )
        }

    @accepts(Str('app_name'), roles=['APPS_READ'])
    @returns(Dict(
        additional_attrs=True,
        example={
            'afb901dc53a29016c385a9de43f089117e399622c042674f82c10c911848baba': {
                'service_name': 'jellyfin',
                'image': 'jellyfin/jellyfin:10.9.7',
                'state': 'running',
                'id': 'afb901dc53a29016c385a9de43f089117e399622c042674f82c10c911848baba',
            }
        }
    ))
    async def container_console_choices(self, app_name):
        """
        Returns container console choices for `app_name`.
        """
        return await self.container_ids(app_name, {'alive_only': True})

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

    @accepts(roles=['CATALOG_READ'])
    @returns(Dict(
        'available_space',
        additional_attrs=True,
        example={
            'parsed': 21289574400,
            'rawvalue': '21289574400',
            'value': '19.8G',
            'source': 'NONE',
            'source_info': None,
        }
    ))
    async def available_space(self):
        """
        Returns space available in the configured apps pool which apps can consume
        """
        await self.middleware.call('docker.state.validate')
        return (await self.middleware.call(
            'zfs.dataset.get_instance', (await self.middleware.call('docker.config'))['dataset'], {
                'extra': {'retrieve_children': False, 'properties': ['available']},
            }
        ))['properties']['available']

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
