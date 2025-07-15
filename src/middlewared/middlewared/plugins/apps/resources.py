from middlewared.api import api_method
from middlewared.api.current import (
    AppContainerIdsArgs, AppContainerIdsResult, AppContainerConsoleChoicesArgs, AppContainerConsoleChoicesResult,
    AppCertificateChoicesArgs, AppCertificateChoicesResult,
    AppUsedPortsArgs, AppUsedPortsResult, AppUsedHostIpsArgs, AppUsedHostIpsResult,
    AppIpChoicesArgs, AppIpChoicesResult, AppAvailableSpaceArgs,
    AppAvailableSpaceResult, AppGpuChoicesArgs, AppGpuChoicesResult,
)
from middlewared.plugins.zfs_.utils import paths_to_datasets_impl
from middlewared.service import private, Service
from middlewared.utils.gpu import get_nvidia_gpus

from .ix_apps.utils import ContainerState
from .resources_utils import get_normalized_gpu_choices
from .utils import IX_APPS_MOUNT_PATH


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @api_method(AppContainerIdsArgs, AppContainerIdsResult, roles=['APPS_READ'])
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

    @api_method(AppContainerConsoleChoicesArgs, AppContainerConsoleChoicesResult, roles=['APPS_READ'])
    async def container_console_choices(self, app_name):
        """
        Returns container console choices for `app_name`.
        """
        return await self.container_ids(app_name, {'alive_only': True})

    @api_method(AppCertificateChoicesArgs, AppCertificateChoicesResult, roles=['APPS_READ'])
    async def certificate_choices(self):
        """
        Returns certificates which can be used by applications.
        """
        return await self.middleware.call(
            'certificate.query', [['cert_type_CSR', '=', False], ['cert_type_CA', '=', False], ['parsed', '=', True]],
            {'select': ['name', 'id']}
        )

    @api_method(AppUsedPortsArgs, AppUsedPortsResult, roles=['APPS_READ'])
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

    @api_method(AppUsedHostIpsArgs, AppUsedHostIpsResult, roles=['APPS_READ'])
    async def used_host_ips(self):
        """
        Returns host IPs in use by applications.
        """
        return sorted(list(set({
            host_ip
            for app in await self.middleware.call('app.query')
            for host_ip in app['active_workloads']['used_host_ips']
        })))

    @api_method(AppIpChoicesArgs, AppIpChoicesResult, roles=['APPS_READ'])
    async def ip_choices(self):
        """
        Returns IP choices which can be used by applications.
        """
        return {
            ip['address']: ip['address']
            for ip in await self.middleware.call('interface.ip_in_use', {'static': True, 'any': True})
        }

    @api_method(AppAvailableSpaceArgs, AppAvailableSpaceResult, roles=['CATALOG_READ'])
    async def available_space(self):
        """
        Returns space available in bytes in the configured apps pool which apps can consume
        """
        await self.middleware.call('docker.state.validate')
        return (await self.middleware.call('filesystem.statfs', IX_APPS_MOUNT_PATH))['avail_bytes']

    @api_method(AppGpuChoicesArgs, AppGpuChoicesResult, roles=['APPS_READ'])
    async def gpu_choices(self):
        """
        Returns GPU choices which can be used by applications.
        """
        return {
            gpu['pci_slot']: {
                k: gpu[k] for k in (
                    'vendor', 'description', 'vendor_specific_config', 'pci_slot', 'error', 'gpu_details',
                )
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

    @private
    async def get_hostpaths_datasets(self, app_name):
        app_info = await self.middleware.call('app.get_instance', app_name)
        host_paths = [
            volume['source'] for volume in app_info['active_workloads']['volumes']
            if volume['source'].startswith(f'{IX_APPS_MOUNT_PATH}/') is False
        ]

        return await self.middleware.run_in_thread(paths_to_datasets_impl, host_paths)
