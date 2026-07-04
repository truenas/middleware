from __future__ import annotations

from typing import TYPE_CHECKING, Any

from truenas_pylibvirt.utils.gpu import get_gpus

from middlewared.alert.source.gpu_isolation import InvalidGpuPciIdsAlert
from middlewared.plugins.initramfs import write_initramfs_flags
from middlewared.plugins.system.reboot import RebootReason
from middlewared.service import ValidationErrors

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


def get_gpu_pci_choices(context: ServiceContext) -> dict[str, Any]:
    configured_value = context.call_sync2(context.s.system.advanced.config).isolated_gpu_pci_ids
    gpus: dict[str, Any] = {}
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


async def update_gpu_pci_ids(context: ServiceContext, isolated_gpu_pci_ids: list[str]) -> None:
    verrors = ValidationErrors()
    if isolated_gpu_pci_ids:
        verrors = await validate_gpu_pci_ids(context, isolated_gpu_pci_ids, verrors, 'gpu_settings')

    if await context.middleware.call('system.is_ha_capable') and isolated_gpu_pci_ids:
        verrors.add(
            'gpu_settings.isolated_gpu_pci_ids',
            'HA capable systems do not support PCI passthrough'
        )

    verrors.check()

    await context.middleware.call(
        'datastore.update',
        'system.advanced',
        (await context.call2(context.s.system.advanced.config)).id,
        {'isolated_gpu_pci_ids': isolated_gpu_pci_ids},
        {'prefix': 'adv_'}
    )
    changed = await context.to_thread(write_initramfs_flags, context.middleware)
    await context.middleware.call('boot.update_initramfs', {'force': changed})


async def validate_gpu_pci_ids(
    context: ServiceContext, isolated_gpu_pci_ids: list[str], verrors: ValidationErrors, schema: str
) -> ValidationErrors:
    available = set()
    critical_gpus = set()
    for gpu in await context.middleware.call('device.get_gpus'):
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


async def validate_isolated_gpus_on_boot(context: ServiceContext) -> None:
    """
    Validates that isolated GPU PCI IDs in the database still point to actual GPUs.
    If a PCI ID no longer points to a GPU (e.g., GPU was removed and PCI ID reassigned),
    it is automatically removed from the isolation configuration and an alert is generated.

    This prevents situations where:
    1. GPU with PCI ID 1 is isolated
    2. GPU is physically removed
    3. On reboot, PCI ID 1 now points to a different device
    4. System incorrectly isolates the wrong device

    Pure validation/cleanup — does not write files or trigger initramfs
    rebuilds. The initramfs.py system.ready handler runs this first, then
    materializes flag files (which will reflect any DB cleanup done here).
    """
    try:
        config = await context.call2(context.s.system.advanced.config)
        isolated_pci_ids = set(config.isolated_gpu_pci_ids)

        if not isolated_pci_ids:
            await context.call2(context.s.alert.oneshot_delete, 'InvalidGpuPciIds', None)
            return

        current_gpu_pci_slots = {
            gpu['addr']['pci_slot'] for gpu in await context.middleware.call('device.get_gpus')
        }
        invalid_pci_ids = isolated_pci_ids - current_gpu_pci_slots

        if not invalid_pci_ids:
            await context.call2(context.s.alert.oneshot_delete, 'InvalidGpuPciIds', None)
            return

        context.logger.warning(
            'Found isolated GPU PCI IDs that no longer point to GPUs: %s', ', '.join(invalid_pci_ids)
        )

        valid_pci_ids = isolated_pci_ids - invalid_pci_ids
        await context.middleware.call(
            'datastore.update',
            'system.advanced',
            config.id,
            {'isolated_gpu_pci_ids': list(valid_pci_ids)},
            {'prefix': 'adv_'}
        )
        context.logger.info(
            'Removed invalid GPU PCI IDs from isolation configuration: %s',
            ', '.join(invalid_pci_ids)
        )

        await context.call2(
            context.s.alert.oneshot_create,
            InvalidGpuPciIdsAlert(pci_ids=', '.join(invalid_pci_ids))
        )
        await context.middleware.call(
            'system.reboot.add_reason',
            RebootReason.GPU_ISOLATION.name,
            RebootReason.GPU_ISOLATION.value,
        )
        context.logger.info('Created alert and added reboot reason for invalid GPU PCI IDs')

    except Exception as e:
        context.logger.error('Error validating isolated GPU PCI IDs on boot: %s', e, exc_info=True)
