from __future__ import annotations

import asyncio
import contextlib
import os

from truenas_pylibvirt import Error as PyLibvirtError
from truenas_pylibvirt import Time, VmBootloader, VmCpuMode, VmVideoModel

from middlewared.api.current import QueryOptions, VMEntry, VMStartOptions, VMStopOptions
from middlewared.service import CallError, ServiceContext
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .info import BOOT_LOADER_OPTIONS, license_active
from .utils import SYSTEM_NVRAM_FOLDER_PATH, SYSTEM_TPM_FOLDER_PATH, get_vm_nvram_file_name, get_vm_tpm_state_dir_name
from .vm_domain import VmDomain, VmDomainConfiguration

LIBVIRT_PROBE_TIMEOUT = 30


async def lifecycle_action_check(context: ServiceContext) -> None:
    if not await license_active(context):
        raise CallError('Requested action cannot be performed as system is not licensed to use VMs')


def start_vm(context: ServiceContext, id_: int, options: VMStartOptions) -> None:
    context.run_coroutine(lifecycle_action_check(context))

    vm = context.call_sync2(context.s.vm.get_instance, id_)
    if vm.status.state in ACTIVE_STATES:
        raise CallError(f'VM {vm.name!r} is already running')

    if vm.bootloader not in BOOT_LOADER_OPTIONS:
        raise CallError(f'"{vm.bootloader}" is not supported on this platform.')

    # Check HA compatibility
    if context.middleware.call_sync('system.is_ha_capable'):
        for device in vm.devices:
            if device.attributes.dtype in ('PCI', 'USB'):
                raise CallError(
                    'Please remove PCI/USB devices from VM before starting it in HA capable machines'
                )

    # Start the VM using pylibvirt
    try:
        context.middleware.libvirt_domains_manager.vms.start(
            pylibvirt_vm(context, vm, options)
        )
    except PyLibvirtError as e:
        raise CallError(str(e))

    # Reload HTTP service for display device changes
    context.call_sync2(context.s.service.control, 'RELOAD', 'http').wait_sync(raise_error=True)


def stop_vm(context: ServiceContext, id_: int, options: VMStopOptions) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    libvirt_domain = pylibvirt_vm(context, vm)
    if options.force:
        context.middleware.libvirt_domains_manager.vms.destroy(libvirt_domain)
        return

    context.middleware.libvirt_domains_manager.vms.shutdown(libvirt_domain, vm.shutdown_timeout)
    if (
        options.force_after_timeout
        and context.call_sync2(context.s.vm.get_instance, id_).status.state == 'RUNNING'
    ):
        context.middleware.libvirt_domains_manager.vms.destroy(libvirt_domain)


def poweroff_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    context.middleware.libvirt_domains_manager.vms.destroy(
        pylibvirt_vm(context, vm)
    )


def reset_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    context.middleware.libvirt_domains_manager.vms.reset(
        pylibvirt_vm(context, vm)
    )


def suspend_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    context.middleware.libvirt_domains_manager.vms.suspend(
        pylibvirt_vm(context, vm)
    )


def resume_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    context.middleware.libvirt_domains_manager.vms.resume(
        pylibvirt_vm(context, vm)
    )


def restart_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    stop_job = context.call_sync2(context.s.vm.stop, id_, VMStopOptions(force_after_timeout=True))
    stop_job.wait_sync()
    if stop_job.error:
        raise CallError(f'Failed to stop {vm.name!r} vm: {stop_job.error}')

    start_vm(context, id_, VMStartOptions(overcommit=True))


def pylibvirt_vm(
    context: ServiceContext, vm: VMEntry, start_config: VMStartOptions | None = None,
) -> VmDomain:
    data = vm.model_dump(expose_secrets=True)
    data.pop('display_available', None)
    data.pop('status', None)
    data.pop('autostart', None)

    device_factory = context.s.vm.device.device_factory
    devices = []
    for device in sorted(data.get('devices', []), key=lambda x: (x['order'], x['id'])):
        devices.append(device_factory.get_device(device))

    data.update({
        'bootloader': VmBootloader(data['bootloader']),
        'video_model': VmVideoModel(data['video_model']),
        'cpu_mode': VmCpuMode(data['cpu_mode']),
        'time': Time(data['time']),
        'nvram_path': os.path.join(SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name(data['id'], data['name'])),
        'tpm_path': os.path.join(SYSTEM_TPM_FOLDER_PATH, get_vm_tpm_state_dir_name(data['id'], data['name'])),
        'devices': devices,
    })

    return VmDomain(
        VmDomainConfiguration(**data),
        context.middleware,
        start_config.model_dump() if start_config is not None else None,
    )


def resume_suspended_vms(context: ServiceContext, vm_ids: list[int]) -> None:
    vms = {vm.id: vm for vm in context.call_sync2(context.s.vm.query)}
    for vm_id in vm_ids:
        vm = vms.get(vm_id)
        if vm is None or vm.status.state != 'SUSPENDED':
            continue
        try:
            resume_vm(context, vm_id)
        except Exception:
            context.logger.error('Failed to resume %r vm', vms[vm_id].name, exc_info=True)


def suspend_vms(context: ServiceContext, vm_ids: list[int]) -> None:
    vms = {vm.id: vm for vm in context.call_sync2(context.s.vm.query)}
    for vm_id in vm_ids:
        vm = vms.get(vm_id)
        if vm is None or vm.status.state != 'RUNNING' or not vm.suspend_on_snapshot:
            continue
        try:
            suspend_vm(context, vm_id)
        except Exception:
            context.logger.error('Failed to suspend %r vm', vms[vm_id].name, exc_info=True)


async def start_on_boot(context: ServiceContext) -> None:
    for vm in await context.call2(context.s.vm.query, [('autostart', '=', True)], QueryOptions(force_sql_filters=True)):
        try:
            await context.to_thread(start_vm, context, vm.id, VMStartOptions())
        except Exception as e:
            context.logger.error(f'Failed to start VM {vm.name}: {e}')


async def active_vms(context: ServiceContext) -> list[VMEntry]:
    # Listing domains starts libvirtd, which vm.query only does once a VM exists.
    if not await context.call2(context.s.vm.query, [], QueryOptions(extra={'retrieve_status': False})):
        return []

    # vm.query reports every VM as STOPPED when libvirt does not answer.
    try:
        await asyncio.wait_for(
            context.to_thread(context.middleware.libvirt_domains_manager.vms_connection.list_domains),
            LIBVIRT_PROBE_TIMEOUT,
        )
    except Exception as e:
        raise CallError(f'libvirt is unreachable: {e!r}') from e

    return await context.call2(context.s.vm.query, [('status.state', 'in', ACTIVE_STATES)])


async def _stop_vm(context: ServiceContext, vm: VMEntry) -> None:
    state = vm.status.state
    if state == 'SUSPENDED':
        # A guest that will not resume cannot shut down cleanly, so it is powered off instead.
        with contextlib.suppress(Exception):
            await context.call2(context.s.vm.resume, vm.id)
        state = (await context.call2(context.s.vm.get_instance, vm.id)).status.state
        if state == 'SUSPENDED':
            await context.to_thread(poweroff_vm, context, vm.id)
            return

    if state == 'RUNNING':
        job = await context.call2(context.s.vm.stop, vm.id, VMStopOptions(force_after_timeout=True))
        await job.wait(raise_error=True)


async def stop_active(context: ServiceContext) -> None:
    vms = await active_vms(context)
    results = await asyncio.gather(*(_stop_vm(context, vm) for vm in vms), return_exceptions=True)
    if failures := [f'{vm.name}: {result}' for vm, result in zip(vms, results) if isinstance(result, BaseException)]:
        raise CallError('VMs not stopped: ' + '; '.join(failures))
