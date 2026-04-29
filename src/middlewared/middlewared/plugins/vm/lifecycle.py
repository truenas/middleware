from __future__ import annotations

import os
import typing

from truenas_pylibvirt import VmBootloader, VmCpuMode

from middlewared.api.current import QueryOptions, VMStartOptions, VMStopOptions
from middlewared.service import CallError, ServiceContext
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .info import BOOT_LOADER_OPTIONS, license_active
from .utils import SYSTEM_NVRAM_FOLDER_PATH, SYSTEM_TPM_FOLDER_PATH, get_vm_nvram_file_name, get_vm_tpm_state_dir_name
from .vm_domain import VmDomain, VmDomainConfiguration


async def lifecycle_action_check(context: ServiceContext) -> None:
    if not await license_active(context):
        raise CallError("Requested action cannot be performed as system is not licensed to use VMs")


def start_vm(context: ServiceContext, id_: int, options: VMStartOptions) -> None:
    context.run_coroutine(lifecycle_action_check(context))

    vm = context.call_sync2(context.s.vm.get_instance, id_)
    if vm.status.state in ACTIVE_STATES:
        raise CallError(f"VM {vm.name!r} is already running")

    if vm.bootloader not in BOOT_LOADER_OPTIONS:
        raise CallError(f'"{vm.bootloader}" is not supported on this platform.')

    # Check HA compatibility
    if context.middleware.call_sync("system.is_ha_capable"):
        for device in vm.devices:
            if device.attributes.dtype in ("PCI", "USB"):
                raise CallError(
                    "Please remove PCI/USB devices from VM before starting it in HA capable machines"
                )

    # Start the VM using pylibvirt
    context.middleware.libvirt_domains_manager.vms.start(
        pylibvirt_vm(context, vm.model_dump(by_alias=True, context={"expose_secrets": True}), options.model_dump())
    )

    # Reload HTTP service for display device changes
    context.middleware.call_sync("service.control", "RELOAD", "http").wait_sync(raise_error=True)


def stop_vm(context: ServiceContext, id_: int, options: VMStopOptions) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    libvirt_domain = pylibvirt_vm(context, vm.model_dump(by_alias=True, context={"expose_secrets": True}))
    if options.force:
        context.middleware.libvirt_domains_manager.vms.destroy(libvirt_domain)
    else:
        context.middleware.libvirt_domains_manager.vms.shutdown(libvirt_domain, vm.shutdown_timeout)


def poweroff_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    context.middleware.libvirt_domains_manager.vms.destroy(
        pylibvirt_vm(context, vm.model_dump(by_alias=True, context={"expose_secrets": True}))
    )


def suspend_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    context.middleware.libvirt_domains_manager.vms.suspend(
        pylibvirt_vm(context, vm.model_dump(by_alias=True, context={"expose_secrets": True}))
    )


def resume_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    context.middleware.libvirt_domains_manager.vms.resume(
        pylibvirt_vm(context, vm.model_dump(by_alias=True, context={"expose_secrets": True}))
    )


def restart_vm(context: ServiceContext, id_: int) -> None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    stop_job = context.call_sync2(context.s.vm.stop, id_, VMStopOptions(force_after_timeout=True))
    stop_job.wait_sync()
    if stop_job.error:
        raise CallError(f"Failed to stop {vm.name!r} vm: {stop_job.error}")

    start_vm(context, id_, VMStartOptions(overcommit=True))


def pylibvirt_vm(
    context: ServiceContext, vm: dict[str, typing.Any], start_config: dict[str, typing.Any] | None = None,
) -> VmDomain:
    vm = vm.copy()
    vm.pop("display_available", None)
    vm.pop("status", None)
    vm.pop("autostart", None)

    device_factory = context.s.vm.device.device_factory
    devices = []
    for device in sorted(vm.get("devices", []), key=lambda x: (x["order"], x["id"])):
        devices.append(device_factory.get_device(device))

    vm.update({
        "bootloader": VmBootloader(vm["bootloader"]),
        "cpu_mode": VmCpuMode(vm["cpu_mode"]),
        "nvram_path": os.path.join(SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name(vm["id"], vm["name"])),
        "tpm_path": os.path.join(SYSTEM_TPM_FOLDER_PATH, get_vm_tpm_state_dir_name(vm["id"], vm["name"])),
        "devices": devices,
    })

    return VmDomain(VmDomainConfiguration(**vm), context.middleware, start_config)


def resume_suspended_vms(context: ServiceContext, vm_ids: list[int]) -> None:
    vms = {vm.id: vm for vm in context.call_sync2(context.s.vm.query)}
    for vm_id in filter(
        lambda v_id: v_id in vms and vms[v_id].status.state == "SUSPENDED",
        vm_ids
    ):
        try:
            resume_vm(context, vm_id)
        except Exception:
            context.logger.error("Failed to resume %r vm", vms[vm_id].name, exc_info=True)


def suspend_vms(context: ServiceContext, vm_ids: list[int]) -> None:
    vms = {vm.id: vm for vm in context.call_sync2(context.s.vm.query)}
    for vm_id in filter(
        lambda v_id: v_id in vms and vms[v_id].status.state == "RUNNING",
        vm_ids
    ):
        try:
            suspend_vm(context, vm_id)
        except Exception:
            context.logger.error("Failed to suspend %r vm", vms[vm_id].name, exc_info=True)


async def start_on_boot(context: ServiceContext) -> None:
    for vm in await context.call2(context.s.vm.query, [("autostart", "=", True)], QueryOptions(force_sql_filters=True)):
        try:
            await context.to_thread(start_vm, context, vm.id, VMStartOptions())
        except Exception as e:
            context.logger.error(f"Failed to start VM {vm.name}: {e}")


async def handle_shutdown(context: ServiceContext) -> None:
    for vm in await context.call2(context.s.vm.query, [("status.state", "in", ACTIVE_STATES)]):
        if vm.status.state == "RUNNING":
            await context.call2(context.s.vm.stop, vm.id, VMStopOptions(force_after_timeout=True))
        else:
            try:
                await context.to_thread(poweroff_vm, context, vm.id)
            except Exception:
                context.logger.error("Powering off %r VM failed", vm.name, exc_info=True)
