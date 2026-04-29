import os

from truenas_os_pyutils.io import atomic_write
from truenas_pylibvirt.utils.gpu import get_gpus

from middlewared.alert.source.gpu_isolation import InvalidGpuPciIdsAlert
from middlewared.api import api_method
from middlewared.api.current import (
    SystemAdvancedGetGpuPciChoicesArgs,
    SystemAdvancedGetGpuPciChoicesResult,
    SystemAdvancedUpdateGpuPciIdsArgs,
    SystemAdvancedUpdateGpuPciIdsResult,
)
from middlewared.plugins.system.reboot import RebootReason
from middlewared.service import Service, ValidationErrors, private


# Flat newline-separated PCI slot list, one slot per line, sorted for stable
# diffing. Lives under /data so it persists across BE upgrades (the installer
# rsyncs /data into the new BE). The initramfs hook copies this file verbatim
# into the initrd as /etc/truenas_vfio_pci_ids, where init-top/truenas_bind_vfio
# reads it line-by-line.
VFIO_PCI_IDS_PATH = '/data/subsystems/initramfs/truenas_vfio_pci_ids'


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
        changed = await self.middleware.call('system.advanced.write_vfio_pci_ids')
        await self.middleware.call('boot.update_initramfs', {'force': changed})

    @private
    def write_vfio_pci_ids(self):
        """
        Materialize the flat list of PCI slots to bind to vfio-pci, expanding
        each chosen GPU into the full set of PCI slots for its sibling functions
        (video + audio + USB-C controller, etc.).

        The initramfs-tools hook /etc/initramfs-tools/hooks/truenas_vfio copies
        this file into the initrd at update-initramfs time;
        init-top/truenas_bind_vfio reads it line-by-line and binds those slots
        to vfio-pci before any host driver can claim them.

        Returns True if the file changed (caller should force an initramfs rebuild).
        """
        igpi = self.middleware.call_sync('system.advanced.config').get('isolated_gpu_pci_ids') or []
        # A "GPU" is actually a group of PCI functions sharing an IOMMU group
        # (video + HDMI audio + sometimes a USB-C controller). All siblings
        # must be bound to vfio-pci together — passthrough fails otherwise —
        # so flatten gpu['devices'] into the slot list.
        slots = []
        for gpu in get_gpus():
            if gpu['addr']['pci_slot'] in igpi:
                for dev in gpu['devices']:
                    slots.append(dev['pci_slot'])

        # Sort so plain text equality is meaningful for change detection,
        # regardless of get_gpus() / sysfs enumeration order.
        new_content = ''.join(f'{s}\n' for s in sorted(slots))

        try:
            with open(VFIO_PCI_IDS_PATH) as f:
                existing_content = f.read()
        except FileNotFoundError:
            existing_content = ''

        if existing_content == new_content:
            return False

        os.makedirs(os.path.dirname(VFIO_PCI_IDS_PATH), exist_ok=True)
        with atomic_write(VFIO_PCI_IDS_PATH, 'w') as f:
            f.write(new_content)
        return True

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
                # Nothing to validate, but still reconcile the on-disk slot list
                # in case it drifted from the database.
                changed = await self.middleware.call('system.advanced.write_vfio_pci_ids')
                if changed:
                    await self.middleware.call('boot.update_initramfs', {'force': True})
                await self.call2(self.s.alert.oneshot_delete, 'InvalidGpuPciIds', None)
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
                changed = await self.middleware.call('system.advanced.write_vfio_pci_ids')
                await self.middleware.call('boot.update_initramfs', {'force': changed})

                self.logger.info(
                    'Removed invalid GPU PCI IDs from isolation configuration: %s',
                    ', '.join(invalid_pci_ids)
                )

                # Create alert to notify user
                await self.call2(
                    self.s.alert.oneshot_create,
                    InvalidGpuPciIdsAlert(pci_ids=', '.join(invalid_pci_ids))
                )

                # Add reboot reason
                await self.middleware.call(
                    'system.reboot.add_reason',
                    RebootReason.GPU_ISOLATION.name,
                    RebootReason.GPU_ISOLATION.value,
                )

                self.logger.info('Created alert and added reboot reason for invalid GPU PCI IDs')
            else:
                # All isolated GPU PCI IDs are valid; reconcile the on-disk
                # slot list so it can't drift from the database.
                changed = await self.middleware.call('system.advanced.write_vfio_pci_ids')
                if changed:
                    await self.middleware.call('boot.update_initramfs', {'force': True})
                await self.call2(self.s.alert.oneshot_delete, 'InvalidGpuPciIds', None)

        except Exception as e:
            self.logger.error('Error validating isolated GPU PCI IDs on boot: %s', e, exc_info=True)


async def _event_system_ready(middleware, event_type, args):
    # We do not want boot to be blocked by this check
    middleware.create_task(middleware.call('system.advanced.validate_isolated_gpus_on_boot'))


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
