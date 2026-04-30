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
from middlewared.utils import run
from middlewared.utils.libvirt.display import DisplayDelegate
from middlewared.utils.libvirt.nic import NICDelegate

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job


BOOT_LOADER_OPTIONS = {
    'UEFI': 'UEFI',
    'UEFI_CSM': 'Legacy BIOS',
}
MAXIMUM_SUPPORTED_VCPUS = 255
RE_AMD_NASID = re.compile(r'NASID:.*\((.*)\)')
RE_VENDOR_AMD = re.compile(r'AuthenticAMD')
RE_VENDOR_INTEL = re.compile(r'GenuineIntel')


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


def supports_virtualization() -> bool:
    return kvm_supported()


async def license_active(context: ServiceContext) -> bool:
    can_run_vms = True
    if await context.middleware.call('system.is_ha_capable'):
        can_run_vms = await context.middleware.call('system.feature_enabled', 'VM')

    return can_run_vms


def virtualization_details() -> VMVirtualizationDetails:
    return VMVirtualizationDetails(
        supported=kvm_supported(),
        error=None if kvm_supported() else 'Your CPU does not support KVM extensions',
    )


async def vm_flags(context: ServiceContext) -> VMFlags:
    flags = VMFlags(
        intel_vmx=False,
        unrestricted_guest=False,
        amd_rvi=False,
        amd_asids=False,
    )
    if not await context.to_thread(supports_virtualization):
        return flags

    cp = await run(['lscpu'], check=False)
    if cp.returncode:
        context.logger.error('Failed to retrieve CPU details: %s', cp.stderr.decode())
        return flags

    if RE_VENDOR_INTEL.findall(cp.stdout.decode()):
        flags.intel_vmx = True
        unrestricted_guest_path = '/sys/module/kvm_intel/parameters/unrestricted_guest'

        def read_unrestricted_guest() -> None:
            if os.path.exists(unrestricted_guest_path):
                with open(unrestricted_guest_path, 'r') as f:
                    flags.unrestricted_guest = f.read().strip().lower() == 'y'

        await context.middleware.run_in_thread(read_unrestricted_guest)
    elif RE_VENDOR_AMD.findall(cp.stdout.decode()):
        flags.amd_rvi = True
        cp = await run(['cpuid', '-l', '0x8000000A'], check=False)
        if cp.returncode:
            context.logger.error('Failed to execute "cpuid -l 0x8000000A": %s', cp.stderr.decode())
        else:
            flags.amd_asids = all(v != '0' for v in (RE_AMD_NASID.findall(cp.stdout.decode()) or ['0']) if v)

    return flags


async def get_console(context: ServiceContext, id_: int) -> str:
    vm = await context.middleware.call('datastore.query', 'vm.vm', [['id', '=', id_]], {'get': True})
    return f'{vm["id"]}_{vm["name"]}'


def cpu_model_choices() -> dict[str, str]:
    return get_cpu_model_choices()


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
