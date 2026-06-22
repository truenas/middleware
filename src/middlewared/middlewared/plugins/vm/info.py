from __future__ import annotations

import functools
import os
import re
import shutil
from socket import AF_INET6
import typing

from truenas_pylibvirt.utils import kvm_supported
from truenas_pylibvirt.utils.cpu import get_cpu_model_choices

from middlewared.api.current import (
    VMDisplayDevice,
    VMDisplayDeviceInfo,
    VMDisplayWebURIOptions,
    VMFlags,
    VMGetDisplayWebUri,
    VMPortWizard,
    VMVirtualizationDetails,
)
from middlewared.service import ServiceContext
from middlewared.utils.cpu import cpu_info
from middlewared.utils.libvirt.display import DisplayDelegate
from middlewared.utils.libvirt.nic import NICDelegate

from .constants import VMGuestArch

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job


BOOT_LOADER_OPTIONS = {
    'UEFI': 'UEFI',
    'UEFI_CSM': 'Legacy BIOS',
}
MAXIMUM_SUPPORTED_VCPUS = 255


def resolution_choices() -> dict[str, str]:
    return {r: r for r in DisplayDelegate.RESOLUTION_ENUM}


async def port_wizard(context: ServiceContext) -> VMPortWizard:
    all_ports: set[int] = await context.middleware.call('port.get_all_used_ports')
    port_iter: typing.Generator[int, None, None] = (p for p in range(5900, 65535) if p not in all_ports)
    return VMPortWizard(port=next(port_iter), web=next(port_iter))


async def all_used_display_device_ports(
    context: ServiceContext, additional_filters: list[typing.Any] | None = None
) -> list[int]:
    all_ports = [6000]
    additional_filters = additional_filters or []
    for device in await context.call2(
        context.s.vm.device.query, [['attributes.dtype', '=', 'DISPLAY']] + additional_filters
    ):
        if not isinstance(device.attributes, VMDisplayDevice):
            continue
        all_ports.extend(p for p in (device.attributes.port, device.attributes.web_port) if p is not None)
    return all_ports


@functools.cache
def bootloader_ovmf_choices() -> dict[str, str]:
    return {path: path for path in os.listdir('/usr/share/OVMF') if re.findall(r'^OVMF_CODE.*.fd', path)}


@functools.cache
def bootloader_aavmf_choices() -> dict[str, str]:
    return {path: path for path in os.listdir('/usr/share/AAVMF') if re.findall(r'^AAVMF_CODE.*.fd', path)}


def random_mac() -> str:
    return NICDelegate.random_mac()


def log_file_path(context: ServiceContext, id_: int) -> str | None:
    vm = context.call_sync2(context.s.vm.get_instance, id_)
    path = f'/var/log/libvirt/qemu/{vm.id}_{vm.name}.log'
    return path if os.path.exists(path) else None


def log_file_download(context: ServiceContext, job: Job, vm_id: int) -> None:
    if path := log_file_path(context, vm_id):
        assert job.pipes.output is not None
        with open(path, 'rb') as f:
            shutil.copyfileobj(f, job.pipes.output.w)


async def license_active(context: ServiceContext) -> bool:
    can_run_vms = True
    if await context.middleware.call('system.is_ha_capable'):
        can_run_vms = await context.middleware.call('system.feature_enabled', 'VMS')

    return can_run_vms


def virtualization_details() -> VMVirtualizationDetails:
    supported = kvm_supported()
    error = None
    if not supported:
        error = 'Your CPU does not support KVM extensions'
    return VMVirtualizationDetails(supported=supported, error=error)


def vm_flags() -> VMFlags:
    flags = VMFlags(
        intel_vmx=False,
        unrestricted_guest=False,
        amd_rvi=False,
        amd_asids=False,
    )
    if not kvm_supported():
        return flags

    ci = cpu_info()  # cpu_info() is cached
    match ci['vendor_id']:
        case 'GenuineIntel':
            flags.intel_vmx = 'vmx' in ci['cpu_flags']
            try:
                with open('/sys/module/kvm_intel/parameters/unrestricted_guest') as f:
                    flags.unrestricted_guest = f.read().strip().lower() == 'y'
            except Exception:
                pass
        case 'AuthenticAMD':
            flags.amd_rvi = 'npt' in ci['cpu_flags']
            flags.amd_asids = 'svm' in ci['cpu_flags']

    return flags


async def get_console(context: ServiceContext, id_: int) -> str:
    vm = await context.middleware.call('datastore.query', 'vm.vm', [['id', '=', id_]], {'get': True})
    return f'{vm["id"]}_{vm["name"]}'


def cpu_model_choices(arch: str = VMGuestArch.X86_64) -> dict[str, str]:
    return get_cpu_model_choices().get(arch, {})


async def get_display_devices(context: ServiceContext, id_: int) -> list[VMDisplayDeviceInfo]:
    devices: list[VMDisplayDeviceInfo] = []
    for device in await context.call2(
        context.s.vm.device.query, [['vm', '=', id_], ['attributes.dtype', '=', 'DISPLAY']]
    ):
        device_dict = device.model_dump(by_alias=True)
        device_dict['attributes']['password_configured'] = bool(device_dict['attributes'].get('password'))
        devices.append(VMDisplayDeviceInfo.model_validate(device_dict))
    return devices


async def get_display_web_uri(
    context: ServiceContext, app: App, id_: int, host: str, options: VMDisplayWebURIOptions,
) -> VMGetDisplayWebUri:
    uri_data = VMGetDisplayWebUri(error=None, uri=None)
    protocol = options.protocol.lower()
    if not host:
        try:
            if app.origin.is_tcp_ip_family and (_h := app.origin.loc_addr):
                host = _h
                if app.origin.family == AF_INET6:
                    host = f'[{_h}]'
        except AttributeError:
            pass

    if display_devices := await get_display_devices(context, id_):
        for device_data in display_devices:
            if device_data.attributes.web:
                uri_data.uri = DisplayDelegate.web_uri(
                    device_data.model_dump(by_alias=True), host, protocol=protocol,
                )
                uri_data.error = None
                break
            else:
                uri_data.error = 'Web display is not configured'
    else:
        uri_data.error = 'Display device is not configured for this VM'

    return uri_data
