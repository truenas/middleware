from truenas_pylibvirt.utils.gpu import get_gpus

from middlewared.api import api_method
from middlewared.api.current import (
    SystemAdvancedGetGpuPciChoicesArgs,
    SystemAdvancedGetGpuPciChoicesResult,
    SystemAdvancedUpdateGpuPciIdsArgs,
    SystemAdvancedUpdateGpuPciIdsResult,
)
from middlewared.service import private, Service, ValidationErrors
from middlewared.plugins.system.reboot import RebootReason


class SystemAdvancedService(Service):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'

    @api_method(
        SystemAdvancedGetGpuPciChoicesArgs,
        SystemAdvancedGetGpuPciChoicesResult,
        roles=['SYSTEM_ADVANCED_READ']
    )
    def get_gpu_pci_choices(self):
        """
        This endpoint gives all the gpu pci ids/slots that can be isolated.
        """
        configured_value = self.middleware.call_sync('system.advanced.config')['isolated_gpu_pci_ids']
        gpus = {}
        gpu_slots = []
        for gpu in get_gpus():
            gpus[f'{gpu["description"]} [{gpu["addr"]["pci_slot"]}]'] = {
                'pci_slot': gpu['addr']['pci_slot'],
                'uses_system_critical_devices': gpu['uses_system_critical_devices'],
                'critical_reason': gpu['critical_reason'],
            }
            gpu_slots.append(gpu['addr']['pci_slot'])

        # uses_system_critical_devices
        for slot in filter(lambda gpu: gpu not in gpu_slots, configured_value):
            gpus[f'Unknown {slot!r} slot'] = {
                'pci_slot': slot,
                'uses_system_critical_devices': False,
                'critical_reason': None,
            }

        return gpus

    @api_method(
        SystemAdvancedUpdateGpuPciIdsArgs,
        SystemAdvancedUpdateGpuPciIdsResult,
        roles=['SYSTEM_ADVANCED_WRITE']
    )
    async def update_gpu_pci_ids(self, isolated_gpu_pci_ids):
        """
        `isolated_gpu_pci_ids` is a list of PCI ids which are isolated from host system.
        """
        verrors = ValidationErrors()
        if isolated_gpu_pci_ids:
            verrors = await self.validate_gpu_pci_ids(isolated_gpu_pci_ids, verrors, 'gpu_settings')

        if await self.middleware.call('system.is_ha_capable') and isolated_gpu_pci_ids:
            verrors.add(
                'gpu_settings.isolated_gpu_pci_ids',
                'HA capable systems do not support PCI passthrough'
            )

        verrors.check()

        await self.middleware.call(
            'datastore.update',
            'system.advanced',
            (await self.middleware.call('system.advanced.config'))['id'],
            {'isolated_gpu_pci_ids': isolated_gpu_pci_ids},
            {'prefix': 'adv_'}
        )
        await self.middleware.call('boot.update_initramfs')

    @private
    async def validate_gpu_pci_ids(self, isolated_gpu_pci_ids, verrors, schema):
        available = set()
        critical_gpus = set()
        for gpu in await self.middleware.call('device.get_gpus'):
            available.add(gpu['addr']['pci_slot'])
            if gpu['uses_system_critical_devices']:
                critical_gpus.add(gpu['addr']['pci_slot'])

        provided = set(isolated_gpu_pci_ids)
        not_available = provided - available
        cannot_isolate = provided & critical_gpus
        if not_available:
            verrors.add(
                f'{schema}.isolated_gpu_pci_ids',
                f'{", ".join(not_available)} GPU pci slot(s) are not available or a GPU is not configured.'
            )

        if cannot_isolate:
            verrors.add(
                f'{schema}.isolated_gpu_pci_ids',
                f'{", ".join(cannot_isolate)} GPU pci slot(s) consists of devices '
                'which cannot be isolated from host.'
            )

        if len(available - provided) < 1:
            verrors.add(
                f'{schema}.isolated_gpu_pci_ids',
                'A minimum of 1 GPU is required for the host to ensure it functions as desired.'
            )

        return verrors

    @private
    async def validate_isolated_gpus_on_boot(self):
        """
        Validates that isolated GPU PCI IDs in the database still point to actual GPUs.
        If a PCI ID no longer points to a GPU (e.g., GPU was removed and PCI ID reassigned),
        it is automatically removed from the isolation configuration and an alert is generated.

        This prevents situations where:
        1. GPU with PCI ID 1 is isolated
        2. GPU is physically removed
        3. On reboot, PCI ID 1 now points to a different device
        4. System incorrectly isolates the wrong device
        """
        try:
            # Get current configuration
            config = await self.middleware.call('system.advanced.config')
            isolated_pci_ids = set(config.get('isolated_gpu_pci_ids', []))

            if not isolated_pci_ids:
                # Nothing to validate
                await self.middleware.call('alert.oneshot_delete', 'InvalidGpuPciIds', None)
                return

            # Get current GPUs in the system
            current_gpu_pci_slots = {gpu['addr']['pci_slot'] for gpu in await self.middleware.call('device.get_gpus')}

            # Find PCI IDs that no longer point to GPUs
            invalid_pci_ids = isolated_pci_ids - current_gpu_pci_slots

            if invalid_pci_ids:
                self.logger.warning(
                    'Found isolated GPU PCI IDs that no longer point to GPUs: %s', ', '.join(invalid_pci_ids)
                )

                # Remove invalid PCI IDs from configuration
                valid_pci_ids = isolated_pci_ids - invalid_pci_ids

                await self.middleware.call(
                    'datastore.update',
                    'system.advanced',
                    config['id'],
                    {'isolated_gpu_pci_ids': list(valid_pci_ids)},
                    {'prefix': 'adv_'}
                )
                await self.middleware.call('boot.update_initramfs')

                self.logger.info(
                    'Removed invalid GPU PCI IDs from isolation configuration: %s',
                    ', '.join(invalid_pci_ids)
                )

                # Create alert to notify user
                await self.middleware.call(
                    'alert.oneshot_create',
                    'InvalidGpuPciIds',
                    {'pci_ids': ', '.join(invalid_pci_ids)}
                )

                # Add reboot reason
                await self.middleware.call(
                    'system.reboot.add_reason',
                    RebootReason.GPU_ISOLATION.name,
                    RebootReason.GPU_ISOLATION.value,
                )

                self.logger.info('Created alert and added reboot reason for invalid GPU PCI IDs')
            else:
                # All isolated GPU PCI IDs are valid, ensure any previous alert is deleted
                await self.middleware.call('alert.oneshot_delete', 'InvalidGpuPciIds', None)

        except Exception as e:
            self.logger.error('Error validating isolated GPU PCI IDs on boot: %s', e, exc_info=True)


async def _event_system_ready(middleware, event_type, args):
    # We do not want boot to be blocked by this check
    middleware.create_task(middleware.call('system.advanced.validate_isolated_gpus_on_boot'))


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
