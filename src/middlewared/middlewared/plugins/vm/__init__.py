from __future__ import annotations

import functools
import typing

from middlewared.api import api_method
from middlewared.api.current import (
    VMBootloaderOptions,
    VMBootloaderOptionsArgs,
    VMBootloaderOptionsResult,
    VMBootloaderOvmfChoicesArgs,
    VMBootloaderOvmfChoicesResult,
    VMCloneArgs,
    VMCloneResult,
    VMCpuModelChoicesArgs,
    VMCpuModelChoicesResult,
    VMCreate,
    VMCreateArgs,
    VMCreateResult,
    VMDeleteArgs,
    VMDeleteOptions,
    VMDeleteResult,
    VMDisplayDeviceInfo,
    VMDisplayWebURIOptions,
    VMEntry,
    VMFlags,
    VMFlagsArgs,
    VMFlagsResult,
    VMGetAvailableMemoryArgs,
    VMGetAvailableMemoryResult,
    VMGetConsoleArgs,
    VMGetConsoleResult,
    VMGetDisplayDevicesArgs,
    VMGetDisplayDevicesResult,
    VMGetDisplayWebUri,
    VMGetDisplayWebUriArgs,
    VMGetDisplayWebUriResult,
    VMGetMemoryUsageArgs,
    VMGetMemoryUsageResult,
    VMGetVmemoryInUse,
    VMGetVmemoryInUseArgs,
    VMGetVmemoryInUseResult,
    VMGetVmMemoryInfo,
    VMGetVmMemoryInfoArgs,
    VMGetVmMemoryInfoResult,
    VMGuestArchitectureAndMachineChoicesArgs,
    VMGuestArchitectureAndMachineChoicesResult,
    VMLogFileDownloadArgs,
    VMLogFileDownloadResult,
    VMLogFilePathArgs,
    VMLogFilePathResult,
    VMMaximumSupportedVcpusArgs,
    VMMaximumSupportedVcpusResult,
    VMPortWizard,
    VMPortWizardArgs,
    VMPortWizardResult,
    VMPoweroffArgs,
    VMPoweroffResult,
    VMRandomMacArgs,
    VMRandomMacResult,
    VMResolutionChoicesArgs,
    VMResolutionChoicesResult,
    VMRestartArgs,
    VMRestartResult,
    VMResumeArgs,
    VMResumeResult,
    VMStartArgs,
    VMStartOptions,
    VMStartResult,
    VMStatus,
    VMStatusArgs,
    VMStatusResult,
    VMStopArgs,
    VMStopOptions,
    VMStopResult,
    VMSupportsVirtualizationArgs,
    VMSupportsVirtualizationResult,
    VMSuspendArgs,
    VMSuspendResult,
    VMUpdate,
    VMUpdateArgs,
    VMUpdateResult,
    VMVirtualizationDetails,
    VMVirtualizationDetailsArgs,
    VMVirtualizationDetailsResult,
)
from middlewared.service import GenericCRUDService, job, private
from middlewared.utils.libvirt.utils import NGINX_PREFIX

from .capabilities import guest_architecture_and_machine_choices
from .clone import clone_vm
from .crud import VMServicePart
from .event import vm_domain_event_callback
from .info import (
    BOOT_LOADER_OPTIONS,
    MAXIMUM_SUPPORTED_VCPUS,
    all_used_display_device_ports,
    bootloader_ovmf_choices,
    cpu_model_choices,
    get_console,
    log_file_download,
    log_file_path,
    port_wizard,
    random_mac,
    resolution_choices,
    supports_virtualization,
    virtualization_details,
    vm_flags,
)
from .info import (
    get_display_devices as _get_display_devices,
)
from .info import (
    get_display_web_uri as _get_display_web_uri,
)
from .lifecycle import (
    handle_shutdown,
    poweroff_vm,
    restart_vm,
    resume_suspended_vms,
    resume_vm,
    start_on_boot,
    start_vm,
    stop_vm,
    suspend_vm,
    suspend_vms,
)
from .memory import (
    get_available_memory,
    get_memory_usage,
    get_vm_memory_info,
    get_vmemory_in_use,
    init_guest_vmemory,
    teardown_guest_vmemory,
)
from .snapshot_tasks import (
    get_vms_to_ignore_for_querying_attachments,
    periodic_snapshot_task_begin,
    query_snapshot_begin,
)
from .vm_device import VMDeviceService

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware
    from middlewared.utils.types import AuditCallback


__all__ = ('VMService',)


class VMService(GenericCRUDService[VMEntry]):

    class Config:
        cli_namespace = 'service.vm'
        entry = VMEntry
        role_prefix = 'VM'
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.device = VMDeviceService(middleware)
        self._svc_part = VMServicePart(self.context)

    @api_method(
        VMCreateArgs,
        VMCreateResult,
        audit='VM create',
        audit_extended=lambda data: data['name'],
        check_annotations=True,
    )
    async def do_create(self, data: VMCreate) -> VMEntry:
        """
        Create a Virtual Machine (VM).

        Maximum of 16 guest virtual CPUs are allowed. By default, every virtual CPU is configured as a
        separate package. Multiple cores can be configured per CPU by specifying `cores` attributes.
        `vcpus` specifies total number of CPU sockets. `cores` specifies number of cores per socket. `threads`
        specifies number of threads per core.

        `ensure_display_device` when set ( the default ) will ensure that the guest always has access to a video device.
        For headless installations like ubuntu server this is required for the guest to operate properly. However
        for cases where consumer would like to use GPU passthrough and does not want a display device added should set
        this to `false`.

        `arch_type` refers to architecture type and can be specified for the guest. By default the value is `null` and
        system in this case will choose a reasonable default based on host.

        `machine_type` refers to machine type of the guest based on the architecture type selected with `arch_type`.
        By default the value is `null` and system in this case will choose a reasonable default based on `arch_type`
        configuration.

        `shutdown_timeout` indicates the time in seconds the system waits for the VM to cleanly shutdown. During system
        shutdown, if the VM hasn't exited after a hardware shutdown signal has been sent by the system within
        `shutdown_timeout` seconds, system initiates poweroff for the VM to stop it.

        `hide_from_msr` is a boolean which when set will hide the KVM hypervisor from standard MSR based discovery and
        is useful to enable when doing GPU passthrough.

        `hyperv_enlightenments` can be used to enable subset of predefined Hyper-V enlightenments for Windows guests.
        These enlightenments improve performance and enable otherwise missing features.

        `suspend_on_snapshot` is a boolean attribute which when enabled will automatically pause/suspend VMs when
        a snapshot is being taken for periodic snapshot tasks. For manual snapshots, if user has specified vms to
        be paused, they will be in that case.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        VMUpdateArgs,
        VMUpdateResult,
        audit='VM update',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: VMUpdate) -> VMEntry:
        """
        Update all information of a specific VM.

        `devices` is a list of virtualized hardware to attach to the virtual machine. If `devices` is not present,
        no change is made to devices. If either the device list order or data stored by the device changes when the
        attribute is passed, these actions are taken:

        1) If there is no device in the `devices` list which was previously attached to the VM, that device is
           removed from the virtual machine.
        2) Devices are updated in the `devices` list when they contain a valid `id` attribute that corresponds to
           an existing device.
        3) Devices that do not have an `id` attribute are created and attached to `id` VM.
        """
        return await self._svc_part.do_update(id_, data, audit_callback=audit_callback)

    @api_method(
        VMDeleteArgs,
        VMDeleteResult,
        audit='VM delete',
        audit_callback=True,
        check_annotations=True,
    )
    def do_delete(self, audit_callback: AuditCallback, id_: int, data: VMDeleteOptions) -> None:
        """
        Delete a VM.
        """
        return self._svc_part.do_delete(id_, data, audit_callback=audit_callback)

    @api_method(
        VMCloneArgs, VMCloneResult, roles=['VM_WRITE'],
        audit='VM clone', audit_callback=True, check_annotations=True,
    )
    async def clone(self, audit_callback: AuditCallback, id_: int, name: str | None) -> bool:
        """
        Clone the VM `id`.

        `name` is an optional parameter for the cloned VM.
        If not provided it will append the next number available to the VM name.
        """
        return await clone_vm(self.context, id_, name, audit_callback=audit_callback)

    @api_method(VMBootloaderOptionsArgs, VMBootloaderOptionsResult, roles=['VM_READ'], check_annotations=True)
    async def bootloader_options(self) -> VMBootloaderOptions:
        """
        Supported motherboard firmware options.
        """
        return VMBootloaderOptions(**BOOT_LOADER_OPTIONS)

    @api_method(VMBootloaderOvmfChoicesArgs, VMBootloaderOvmfChoicesResult, roles=['VM_READ'], check_annotations=True)
    def bootloader_ovmf_choices(self) -> dict[str, str]:
        """
        Retrieve bootloader ovmf choices
        """
        return bootloader_ovmf_choices()

    @api_method(VMCpuModelChoicesArgs, VMCpuModelChoicesResult, roles=['VM_READ'], check_annotations=True)
    def cpu_model_choices(self) -> dict[str, str]:
        """
        Retrieve CPU Model choices which can be used with a VM guest to emulate the CPU in the guest.
        """
        return cpu_model_choices()

    @api_method(VMFlagsArgs, VMFlagsResult, roles=['VM_READ'], check_annotations=True)
    async def flags(self) -> VMFlags:
        """
        Returns a dictionary with CPU flags for the hypervisor.
        """
        return await vm_flags(self.context)

    @api_method(VMGetAvailableMemoryArgs, VMGetAvailableMemoryResult, roles=['VM_READ'], check_annotations=True)
    async def get_available_memory(self, overcommit: bool) -> int:
        """
        Get the current maximum amount of available memory to be allocated for VMs.

        In case of `overcommit` being `true`, calculations are done in the following manner:
        1. If a VM has requested 10G but is only consuming 5G, only 5G will be counted
        2. System will consider shrinkable ZFS ARC as free memory ( shrinkable ZFS ARC is current ZFS ARC
           minus ZFS ARC minimum )

        In case of `overcommit` being `false`, calculations are done in the following manner:
        1. Complete VM requested memory will be taken into account regardless of how much actual physical
           memory the VM is consuming
        2. System will not consider shrinkable ZFS ARC as free memory

        Memory is of course a very "volatile" resource, values may change abruptly between a
        second but I deem it good enough to give the user a clue about how much memory is
        available at the current moment and if a VM should be allowed to be launched.
        """
        return await get_available_memory(self.context, overcommit)

    @api_method(VMGetConsoleArgs, VMGetConsoleResult, roles=['VM_READ'], check_annotations=True)
    async def get_console(self, id_: int) -> str:
        """
        Get the console device from a given guest.
        """
        return await get_console(self.context, id_)

    @api_method(VMGetDisplayDevicesArgs, VMGetDisplayDevicesResult, roles=['VM_READ'], check_annotations=True)
    async def get_display_devices(self, id_: int) -> list[VMDisplayDeviceInfo]:
        """
        Get the display devices from a given guest. If a display device has password configured,
        `attributes.password_configured` will be set to `true`.
        """
        return await _get_display_devices(self.context, id_)

    @api_method(
        VMGetDisplayWebUriArgs, VMGetDisplayWebUriResult, roles=['VM_READ'],
        pass_app=True, check_annotations=True,
    )
    async def get_display_web_uri(
        self, app: App, id_: int, host: str, options: VMDisplayWebURIOptions
    ) -> VMGetDisplayWebUri:
        """
        Retrieve Display URI for a given VM or appropriate error if there is no display device available
        or if it is not configured to use web interface.
        """
        return await _get_display_web_uri(self.context, app, id_, host, options)

    @api_method(VMGetMemoryUsageArgs, VMGetMemoryUsageResult, roles=['VM_READ'], check_annotations=True)
    def get_memory_usage(self, id_: int) -> int:
        """
        Get the memory usage of a given VM.
        """
        return get_memory_usage(self.context, id_)

    @api_method(VMGetVmMemoryInfoArgs, VMGetVmMemoryInfoResult, roles=['VM_READ'], check_annotations=True)
    async def get_vm_memory_info(self, vm_id: int) -> VMGetVmMemoryInfo:
        """
        Returns memory information for `vm_id` VM if it is going to be started.

        All memory attributes are expressed in bytes.
        """
        return await get_vm_memory_info(self.context, vm_id)

    @api_method(VMGetVmemoryInUseArgs, VMGetVmemoryInUseResult, roles=['VM_READ'], check_annotations=True)
    async def get_vmemory_in_use(self) -> VMGetVmemoryInUse:
        """
        The total amount of virtual memory in bytes used by guests

            Returns a dict with the following information:
                RNP - Running but not provisioned
                PRD - Provisioned but not running
                RPRD - Running and provisioned
        """
        return await get_vmemory_in_use(self.context)

    @api_method(
        VMGuestArchitectureAndMachineChoicesArgs,
        VMGuestArchitectureAndMachineChoicesResult,
        roles=['VM_READ'],
        check_annotations=True,
    )
    def guest_architecture_and_machine_choices(self) -> dict[str, list[str]]:
        """
        Retrieve choices for supported guest architecture types and machine choices.

        Keys in the response would be supported guest architecture(s) on the host and their respective values would
        be supported machine type(s) for the specific architecture on the host.
        """
        return guest_architecture_and_machine_choices(self.context)

    @api_method(VMLogFileDownloadArgs, VMLogFileDownloadResult, roles=['VM_READ'], check_annotations=True)
    @job(pipes=['output'])
    def log_file_download(self, job: Job, vm_id: int) -> None:
        """
        Retrieve log file contents of `id` VM.

        It will download empty file if log file does not exist.
        """
        log_file_download(self.context, job, vm_id)

    @api_method(VMLogFilePathArgs, VMLogFilePathResult, roles=['VM_READ'], check_annotations=True)
    def log_file_path(self, vm_id: int) -> str | None:
        """
        Retrieve log file path of `id` VM.

        It will return path of the log file if it exists and `null` otherwise.
        """
        return log_file_path(self.context, vm_id)

    @api_method(VMMaximumSupportedVcpusArgs, VMMaximumSupportedVcpusResult, roles=['VM_READ'], check_annotations=True)
    async def maximum_supported_vcpus(self) -> int:
        """
        Returns maximum supported VCPU's
        """
        return MAXIMUM_SUPPORTED_VCPUS

    @api_method(VMPortWizardArgs, VMPortWizardResult, roles=['VM_READ'], check_annotations=True)
    async def port_wizard(self) -> VMPortWizard:
        """
        It returns the next available Display Server Port and Web Port.

        Returns a dict with two keys `port` and `web`.
        """
        return await port_wizard(self.context)

    @api_method(VMPoweroffArgs, VMPoweroffResult, roles=['VM_WRITE'], check_annotations=True)
    def poweroff(self, id_: int) -> None:
        """
        Poweroff a VM.
        """
        poweroff_vm(self.context, id_)

    @api_method(VMRandomMacArgs, VMRandomMacResult, roles=['VM_READ'], check_annotations=True)
    def random_mac(self) -> str:
        """
        Create a random mac address.

        Returns:
            str: with six groups of two hexadecimal digits
        """
        return random_mac()

    @api_method(VMResolutionChoicesArgs, VMResolutionChoicesResult, roles=['VM_READ'], check_annotations=True)
    async def resolution_choices(self) -> dict[str, str]:
        """
        Retrieve supported resolution choices for VM Display devices.
        """
        return resolution_choices()

    @api_method(VMRestartArgs, VMRestartResult, roles=['VM_WRITE'], check_annotations=True)
    @job(lock=lambda args: f'restart_vm_{args[0]}')
    def restart(self, job: Job, id_: int) -> None:
        """
        Restart a VM.
        """
        restart_vm(self.context, id_)

    @api_method(VMResumeArgs, VMResumeResult, roles=['VM_WRITE'], check_annotations=True)
    def resume(self, id_: int) -> None:
        """
        Resume suspended `id` VM.
        """
        resume_vm(self.context, id_)

    @api_method(VMStartArgs, VMStartResult, roles=['VM_WRITE'], check_annotations=True)
    def start(self, id_: int, options: VMStartOptions) -> None:
        """
        Start a VM.

        options.overcommit defaults to false, meaning VMs are not allowed to
        start if there is not enough available memory to hold all configured VMs.
        If true, VM starts even if there is not enough memory for all configured VMs.

        Error codes:

            ENOMEM(12): not enough free memory to run the VM without overcommit
        """
        start_vm(self.context, id_, options)

    @api_method(VMStatusArgs, VMStatusResult, roles=['VM_READ'], check_annotations=True)
    async def status(self, id_: int) -> VMStatus:
        """
        Get the status of `id` VM.

        Returns a dict:
            - state, RUNNING / STOPPED / SUSPENDED
            - pid, process id if RUNNING
        """
        return (await self.middleware.call2(self.s.vm.get_instance, id_)).status

    @api_method(VMStopArgs, VMStopResult, roles=['VM_WRITE'], check_annotations=True)
    @job(lock=lambda args: f'stop_vm_{args[0]}')
    def stop(self, job: Job, id_: int, options: VMStopOptions) -> None:
        """
        Stops a VM.

        For unresponsive guests who have exceeded the `shutdown_timeout` defined by the user and have become
        unresponsive, they required to be powered down using `vm.poweroff`. `vm.stop` is only going to send a
        shutdown signal to the guest and wait the desired `shutdown_timeout` value before tearing down guest vmemory.

        `force_after_timeout` when supplied, it will initiate poweroff for the VM forcing it to exit if it has
        not already stopped within the specified `shutdown_timeout`.
        """
        stop_vm(self.context, id_, options)

    @api_method(
        VMSupportsVirtualizationArgs,
        VMSupportsVirtualizationResult,
        roles=['VM_READ'],
        check_annotations=True
    )
    def supports_virtualization(self) -> bool:
        """
        Returns "true" if system supports virtualization, "false" otherwise
        """
        return supports_virtualization()

    @api_method(VMSuspendArgs, VMSuspendResult, roles=['VM_WRITE'], check_annotations=True)
    def suspend(self, id_: int) -> None:
        """
        Suspend `id` VM.
        """
        suspend_vm(self.context, id_)

    @api_method(VMVirtualizationDetailsArgs, VMVirtualizationDetailsResult, roles=['VM_READ'], check_annotations=True)
    def virtualization_details(self) -> VMVirtualizationDetails:
        """
        Retrieve details if virtualization is supported on the system and in case why it's not supported if it isn't.
        """
        return virtualization_details()

    @private
    async def all_used_display_device_ports(self, additional_filters: list[typing.Any] | None = None) -> list[int]:
        return await all_used_display_device_ports(self.context, additional_filters)

    @private
    async def get_vm_display_nginx_route(self) -> str:
        return NGINX_PREFIX

    @private
    async def get_vms_to_ignore_for_querying_attachments(
        self, enabled: bool, extra_filters: list[typing.Any] | None = None
    ) -> list[int]:
        return await get_vms_to_ignore_for_querying_attachments(self.context, enabled, extra_filters)

    @private
    async def handle_shutdown(self) -> None:
        await handle_shutdown(self.context)

    @private
    async def init_guest_vmemory(self, vm_id: int, overcommit: bool) -> None:
        await init_guest_vmemory(self.context, vm_id, overcommit)

    @private
    async def query_snapshot_begin(self, dataset: str, recursive: bool) -> dict[int, list[dict[str, typing.Any]]]:
        return await query_snapshot_begin(self.context, dataset, recursive)

    @private
    async def periodic_snapshot_task_begin(self, task_id: int) -> dict[int, list[dict[str, typing.Any]]]:
        return await periodic_snapshot_task_begin(self.context, task_id)

    @private
    def resume_suspended_vms(self, vm_ids: list[int]) -> None:
        resume_suspended_vms(self.context, vm_ids)

    @private
    async def start_on_boot(self) -> None:
        await start_on_boot(self.context)

    @private
    def suspend_vms(self, vm_ids: list[int]) -> None:
        suspend_vms(self.context, vm_ids)

    @private
    async def teardown_guest_vmemory(self, vm_id: int) -> None:
        await teardown_guest_vmemory(self.context, vm_id)


async def __event_system_ready(middleware: Middleware, event_type: str, args: typing.Any) -> None:
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service, however, the VMs still need to be
    # initialized (which is what the above callers are doing)
    if await middleware.call('failover.licensed'):
        return

    middleware.create_task(middleware.call2(middleware.services.vm.start_on_boot))


async def __event_system_shutdown(middleware: Middleware, event_type: str, args: typing.Any) -> None:
    await middleware.call2(middleware.services.vm.handle_shutdown)


async def setup(middleware: Middleware) -> None:
    # it's _very_ important that we run this before we do
    # any type of VM initialization. We have to capture the
    # zfs c_max value before we start manipulating these
    # sysctls during vm start/stop
    await middleware.call('sysctl.store_default_arc_max')

    middleware.event_subscribe('system.ready', __event_system_ready)
    middleware.event_subscribe('system.shutdown', __event_system_shutdown)
    middleware.libvirt_domains_manager.vms.connection.register_domain_event_callback(
        functools.partial(vm_domain_event_callback, middleware)
    )
