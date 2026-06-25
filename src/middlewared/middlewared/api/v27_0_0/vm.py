from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    IPvAnyAddress,
    NonEmptyString,
    UUIDv4String,
    excluded_field,
)

from .vm_device import VMDeviceEntry, VMDisplayDevice

__all__ = [
    'VMEntry', 'VMCreateArgs', 'VMCreateResult', 'VMUpdateArgs', 'VMUpdateResult', 'VMDeleteArgs', 'VMDeleteResult',
    'VMBootloaderOvmfChoicesArgs', 'VMBootloaderOvmfChoicesResult',
    'VMBootloaderAavmfChoicesArgs', 'VMBootloaderAavmfChoicesResult',
    'VMBootloaderOptionsArgs',
    'VMBootloaderOptionsResult', 'VMStatusArgs', 'VMStatusResult', 'VMLogFilePathArgs', 'VMLogFilePathResult',
    'VMLogFileDownloadArgs', 'VMLogFileDownloadResult', 'VMGuestArchitectureAndMachineChoicesArgs',
    'VMGuestArchitectureAndMachineChoicesResult', 'VMCloneArgs', 'VMCloneResult',
    'VMSupportsVirtualizationArgs', 'VMDisplayDeviceInfo', 'VMGetDisplayWebUri', 'VMDisplayWebURIOptions',
    'VMSupportsVirtualizationResult', 'VMVirtualizationDetailsArgs', 'VMVirtualizationDetailsResult',
    'VMMaximumSupportedVcpusArgs', 'VMMaximumSupportedVcpusResult', 'VMFlagsArgs', 'VMFlagsResult', 'VMGetConsoleArgs',
    'VMGetConsoleResult', 'VMCpuModelChoicesArgs', 'VMCpuModelChoicesResult', 'VMGetMemoryUsageArgs',
    'VMGetMemoryUsageResult', 'VMPortWizardArgs', 'VMPortWizardResult', 'VMResolutionChoicesArgs',
    'VMResolutionChoicesResult', 'VMGetDisplayDevicesArgs', 'VMGetDisplayDevicesResult', 'VMGetDisplayWebUriArgs',
    'VMGetDisplayWebUriResult', 'VMStartArgs', 'VMStartResult', 'VMStopArgs', 'VMStopResult', 'VMRestartArgs',
    'VMRestartResult', 'VMResumeArgs', 'VMResumeResult', 'VMPoweroffArgs', 'VMPoweroffResult', 'VMSuspendArgs',
    'VMSuspendResult', 'VMGetVmemoryInUseArgs', 'VMGetVmemoryInUseResult', 'VMGetAvailableMemoryArgs',
    'VMGetAvailableMemoryResult', 'VMGetVmMemoryInfoArgs', 'VMGetVmMemoryInfoResult', 'VMRandomMacArgs',
    'VMRandomMacResult', 'VMCreate', 'VMUpdate', 'VMDeleteOptions', 'VMVirtualizationDetails', 'VMFlags',
    'VMGetVmemoryInUse', 'VMStatus', 'VMGetVmMemoryInfo', 'VMStartOptions', 'VMStopOptions', 'VMPortWizard',
    'VMBootloaderOptions',
    'VMGuestNetworkInterfaceIPAddress', 'VMGuestNetworkInterface',
    'VMGetGuestNetworkInterfacesArgs', 'VMGetGuestNetworkInterfacesResult',
]


class VMStatus(BaseModel):
    state: NonEmptyString = Field(
        examples=["RUNNING", "STOPPED", "SUSPENDED"],
        description="Current state of the virtual machine.",
    )
    pid: int | None = Field(description="Process ID of the running VM. `null` if not running.")
    domain_state: NonEmptyString | None = Field(description="Hypervisor-specific domain state.")


class VMEntry(BaseModel):
    command_line_args: str = Field(
        default='',
        description="Additional command line arguments passed to the VM hypervisor.",
    )
    cpu_mode: Literal['CUSTOM', 'HOST-MODEL', 'HOST-PASSTHROUGH'] = Field(
        default='CUSTOM',
        description=(
            "CPU virtualization mode.\n"
            "\n"
            "* `CUSTOM`: Use specified model.\n"
            "* `HOST-MODEL`: Mirror host CPU.\n"
            "* `HOST-PASSTHROUGH`: Provide direct access to host CPU features."
        ),
    )
    cpu_model: str | None = Field(
        default=None,
        description="Specific CPU model to emulate. `null` to use hypervisor default.",
    )
    name: NonEmptyString = Field(description="Display name of the virtual machine.")
    description: str = Field(default='', description="Optional description or notes about the virtual machine.")
    vcpus: int = Field(
        ge=1,
        default=1,
        description=(
            "Number of virtual CPU sockets. The total number of guest vCPUs is `vcpus` * `cores` * `threads` "
            "(maximum 16)."
        ),
    )
    cores: int = Field(ge=1, default=1, description="Number of CPU cores per socket.")
    threads: int = Field(ge=1, default=1, description="Number of threads per CPU core.")
    cpuset: str | None = Field(
        default=None,
        description="Set of host CPU cores to pin VM CPUs to. `null` for no pinning.",
    )  # TODO: Add validation for numeric set
    nodeset: str | None = Field(
        default=None,
        description="Set of NUMA nodes to constrain VM memory allocation. `null` for no constraints.",
    )  # TODO: Same as above
    enable_cpu_topology_extension: bool = Field(
        default=False,
        description="Whether to expose detailed CPU topology information to the guest OS.",
    )
    pin_vcpus: bool = Field(
        default=False,
        description=(
            "Whether to pin virtual CPUs to specific host CPU cores. Improves performance but reduces host flexibility."
        ),
    )
    suspend_on_snapshot: bool = Field(
        default=True,
        description=(
            "Whether to automatically suspend the VM when a periodic snapshot task runs. For manual snapshots, "
            "the VM is suspended only if explicitly included in the snapshot's VM pause list."
        ),
    )
    trusted_platform_module: bool = Field(
        default=False,
        description="Whether to enable virtual Trusted Platform Module (TPM) for the VM.",
    )
    memory: int = Field(ge=20, description="Amount of memory allocated to the VM in mebibytes (MiB).")
    min_memory: int | None = Field(
        ge=20,
        default=None,
        description=(
            "Minimum memory allocation for dynamic memory ballooning in mebibytes (MiB). Allows VM memory to shrink "
            "during low usage but guarantees this minimum. `null` to disable ballooning."
        ),
    )
    hyperv_enlightenments: bool = Field(
        default=False,
        description="Whether to enable Hyper-V enlightenments for improved Windows guest performance.",
    )
    bootloader: Literal['UEFI_CSM', 'UEFI'] = Field(
        default='UEFI',
        description="Boot firmware type. `UEFI` for modern UEFI, `UEFI_CSM` for legacy BIOS compatibility.",
    )
    bootloader_ovmf: str = Field(
        default='OVMF_CODE.fd',
        examples=['OVMF_CODE.fd', 'OVMF_CODE.secboot.fd'],
        description="OVMF firmware file to use for UEFI boot.",
    )
    autostart: bool = Field(
        default=True,
        description="Whether to automatically start the VM when the host system boots.",
    )
    hide_from_msr: bool = Field(
        default=False,
        description=(
            "Whether to hide the KVM hypervisor from standard MSR-based discovery. Useful when doing GPU passthrough."
        ),
    )
    ensure_display_device: bool = Field(
        default=True,
        description=(
            "Whether to ensure the guest always has access to a video device. Required for headless OS installations "
            "(e.g. Ubuntu Server). Set to `false` when using GPU passthrough without a separate display device."
        ),
    )
    time: Literal['LOCAL', 'UTC'] = Field(
        default='LOCAL',
        description="Guest OS time zone reference. `LOCAL` uses host timezone, `UTC` uses coordinated universal time.",
    )
    shutdown_timeout: int = Field(
        ge=5,
        le=300,
        default=90,
        description=(
            "Maximum time in seconds to wait for graceful shutdown before forcing power off. Default 90s balances "
            "allowing sufficient time for clean shutdown while avoiding indefinite hangs."
        ),
    )
    arch_type: str | None = Field(
        default=None,
        description="Guest architecture type. `null` to use hypervisor default.",
    )
    machine_type: str | None = Field(
        default=None,
        description="Virtual machine type/chipset. `null` to use hypervisor default.",
    )
    uuid: UUIDv4String = Field(description="Unique UUID for the VM.")
    devices: list[VMDeviceEntry] = Field(description="Array of virtual devices attached to this VM.")
    display_available: bool = Field(description="Whether at least one display device is available for this VM.")
    id: int = Field(description="Unique identifier for the virtual machine.")
    status: VMStatus = Field(description="Current runtime status information for the VM.")
    enable_secure_boot: bool = Field(
        default=False,
        description="Whether to enable UEFI Secure Boot for enhanced security.",
    )


class VMCreate(VMEntry):
    status: Excluded = excluded_field()
    id: Excluded = excluded_field()
    display_available: Excluded = excluded_field()
    devices: Excluded = excluded_field()
    uuid: UUIDv4String | None = Field(default=None, description="Unique UUID for the VM. `null` to auto-generate.")
    bootloader_ovmf: str | None = Field(
        default=None,
        examples=['OVMF_CODE.fd', 'OVMF_CODE.secboot.fd'],
        description="OVMF firmware file to use for UEFI boot.",
    )


class VMCreateArgs(BaseModel):
    vm_create: VMCreate = Field(description="VM creation parameters.")


class VMCreateResult(BaseModel):
    result: VMEntry = Field(description="The newly created virtual machine configuration.")


class VMUpdate(VMCreate, metaclass=ForUpdateMetaclass):
    bootloader_ovmf: Excluded = excluded_field()
    enable_secure_boot: Excluded = excluded_field()


class VMUpdateArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to update.")
    vm_update: VMUpdate = Field(description="Updated configuration for the virtual machine.")


class VMUpdateResult(BaseModel):
    result: VMEntry = Field(description="The updated virtual machine configuration.")


class VMDeleteOptions(BaseModel):
    zvols: bool = Field(default=False, description="Delete associated ZFS volumes when deleting the VM.")
    force: bool = Field(default=False, description="Force deletion even if the VM is currently running.")


class VMDeleteArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to delete.")
    options: VMDeleteOptions = Field(
        default=VMDeleteOptions(),
        description="Options controlling the VM deletion process.",
    )


class VMDeleteResult(BaseModel):
    result: None


class VMBootloaderOvmfChoicesArgs(BaseModel):
    pass


class VMBootloaderOvmfChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Available OVMF firmware files for UEFI booting.")


class VMBootloaderAavmfChoicesArgs(BaseModel):
    pass


class VMBootloaderAavmfChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Available AAVMF firmware files for aarch64 UEFI booting.")


class VMBootloaderOptionsArgs(BaseModel):
    pass


class VMBootloaderOptions(BaseModel):
    UEFI: Literal['UEFI'] = Field(default='UEFI', description="Modern UEFI firmware with secure boot support.")
    UEFI_CSM: Literal['Legacy BIOS'] = Field(
        default='Legacy BIOS',
        description="UEFI with Compatibility Support Module for legacy BIOS compatibility.",
    )


class VMBootloaderOptionsResult(BaseModel):
    result: VMBootloaderOptions = Field(description="Supported motherboard firmware options.")


class VMStatusArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get status for.")


class VMStatusResult(BaseModel):
    result: VMStatus = Field(description="Current status and runtime information for the virtual machine.")


class VMLogFilePathArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get log file path for.")


class VMLogFilePathResult(BaseModel):
    result: NonEmptyString | None = Field(description="Path to the VM log file. `null` if no log file exists.")


class VMLogFileDownloadArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to download log file for.")


class VMLogFileDownloadResult(BaseModel):
    result: None


class VMGuestArchitectureAndMachineChoicesArgs(BaseModel):
    pass


class VMGuestArchitectureAndMachineChoicesResult(BaseModel):
    result: dict[str, list[str]] = Field(description="VM Guest architecture and machine choices.")


class VMCloneArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to clone.")
    name: NonEmptyString | None = Field(
        default=None,
        description=(
            "Name for the cloned virtual machine. "
            "`null` to append the next available number to the original VM name."
        ),
    )


class VMCloneResult(BaseModel):
    result: bool = Field(description="Whether the virtual machine was successfully cloned.")


class VMSupportsVirtualizationArgs(BaseModel):
    pass


class VMSupportsVirtualizationResult(BaseModel):
    result: bool = Field(description="Whether the host system supports hardware virtualization (VT-x/AMD-V).")


class VMVirtualizationDetailsArgs(BaseModel):
    pass


class VMVirtualizationDetails(BaseModel):
    supported: bool = Field(description="Whether hardware virtualization is supported and available.")
    error: str | None = Field(description="Error message if virtualization is not available. `null` if supported.")


class VMVirtualizationDetailsResult(BaseModel):
    result: VMVirtualizationDetails = Field(description="VM Virtualization details.")


class VMMaximumSupportedVcpusArgs(BaseModel):
    pass


class VMMaximumSupportedVcpusResult(BaseModel):
    result: int = Field(description="Maximum number of virtual CPUs supported by the host system.")


class VMFlagsArgs(BaseModel):
    pass


class VMFlags(BaseModel):
    intel_vmx: bool = Field(description="Whether Intel VT-x (VMX) virtualization is available.")
    unrestricted_guest: bool = Field(description="Whether Intel unrestricted guest mode is supported.")
    amd_rvi: bool = Field(description="Whether AMD Rapid Virtualization Indexing (RVI/NPT) is available.")
    amd_asids: bool = Field(description="Whether AMD Address Space Identifiers (ASIDs) are supported.")


class VMFlagsResult(BaseModel):
    result: VMFlags = Field(description="VM Flags.")


class VMGetConsoleArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get console connection information for.")


class VMGetConsoleResult(BaseModel):
    result: NonEmptyString = Field(description="Console connection string or command for accessing the VM console.")


class VMCpuModelChoicesArgs(BaseModel):
    arch: str = Field(
        default='x86_64',
        description="Guest architecture to return CPU model choices for (e.g. 'x86_64', 'aarch64').",
    )


class VMCpuModelChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Available CPU models for virtual machine emulation.")


class VMGetMemoryUsageArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get memory usage for.")


class VMGetMemoryUsageResult(BaseModel):
    result: int = Field(description="Current memory usage of the virtual machine in bytes.")


class VMPortWizardArgs(BaseModel):
    pass


class VMPortWizard(BaseModel):
    port: int = Field(description="Available server port.")
    web: int = Field(description="Web port to be used based on available port.")


class VMPortWizardResult(BaseModel):
    result: VMPortWizard = Field(description="VM port wizard.")


class VMResolutionChoicesArgs(BaseModel):
    pass


class VMResolutionChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Object of available display resolutions for virtual machines.")


class VMGetDisplayDevicesArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get display devices for.")


class GetDisplayDevice(VMDisplayDevice):
    password_configured: bool = Field(description="Whether a password has been configured for display access.")


class VMDisplayDeviceInfo(VMDeviceEntry):
    attributes: GetDisplayDevice = Field(
        description="Display device attributes including password configuration status.",
    )


class VMGetDisplayDevicesResult(BaseModel):
    result: list[VMDisplayDeviceInfo] = Field(
        description="Array of display devices configured for the virtual machine.",
    )


class VMDisplayWebURIOptions(BaseModel):
    protocol: Literal['HTTP', 'HTTPS'] = Field(
        default='HTTP',
        description="Protocol to use for the web display URI (HTTP or HTTPS).",
    )


class VMGetDisplayWebUriArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get display web URI for.")
    host: str = Field(
        default='',
        description="Hostname or IP address to use in the URI. Empty string for automatic detection.",
    )
    options: VMDisplayWebURIOptions = Field(
        default=VMDisplayWebURIOptions(),
        description="Options for generating the web display URI.",
    )


class VMGetDisplayWebUri(BaseModel):
    error: str | None = Field(description="Error message if URI generation failed. `null` on success.")
    uri: str | None = Field(description="Generated web URI for accessing the VM display. `null` on error.")


class VMGetDisplayWebUriResult(BaseModel):
    result: VMGetDisplayWebUri = Field(description="VM display web URI for accessing the VM display.")


class VMStartOptions(BaseModel):
    overcommit: bool = Field(default=False, description="Whether to allow memory overcommitment when starting the VM.")


class VMStartArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to start.")
    options: VMStartOptions = Field(default=VMStartOptions(), description="Options controlling the VM start process.")


class VMStartResult(BaseModel):
    result: None = Field(description="Returns `null` on successful VM start initiation.")


class VMStopOptions(BaseModel):
    force: bool = Field(
        default=False,
        description="Whether to force immediate shutdown without graceful shutdown attempt.",
    )
    force_after_timeout: bool = Field(
        default=False,
        description="Whether to force shutdown if graceful shutdown times out.",
    )


class VMStopArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to stop.")
    options: VMStopOptions = Field(default=VMStopOptions(), description="Options controlling the VM stop process.")


class VMStopResult(BaseModel):
    result: None = Field(description="Returns `null` on successful VM stop initiation.")


class VMPoweroffArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to power off forcefully.")


class VMPoweroffResult(BaseModel):
    result: None = Field(description="Returns `null` on successful VM power off initiation.")


class VMRestartArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to restart.")


class VMRestartResult(BaseModel):
    result: None = Field(description="Returns `null` on successful VM restart initiation.")


class VMSuspendArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to suspend.")


class VMSuspendResult(BaseModel):
    result: None = Field(description="Returns `null` on successful VM suspend initiation.")


class VMResumeArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to resume from suspended state.")


class VMResumeResult(BaseModel):
    result: None = Field(description="Returns `null` on successful VM resume initiation.")


class VMGetVmemoryInUseArgs(BaseModel):
    pass


class VMGetVmemoryInUse(BaseModel):
    RNP: int = Field(description="Running but not provisioned, in bytes.")
    PRD: int = Field(description="Provisioned but not running, in bytes.")
    RPRD: int = Field(description="Running and provisioned, in bytes.")


class VMGetVmemoryInUseResult(BaseModel):
    result: VMGetVmemoryInUse = Field(description="VM get vmemory inuse details.")


class VMGetAvailableMemoryArgs(BaseModel):
    overcommit: bool = Field(
        default=False,
        description="Whether to include overcommitted memory in available memory calculation.",
    )


class VMGetAvailableMemoryResult(BaseModel):
    result: int = Field(description="Available memory for virtual machines in bytes.")


class VMGetVmMemoryInfoArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get memory information for.")


class VMGetVmMemoryInfo(BaseModel):
    minimum_memory_requested: int | None = Field(description="Minimum memory requested by the VM.")
    total_memory_requested: int = Field(description="Maximum / total memory requested by the VM.")
    overcommit_required: bool = Field(description="Overcommit of memory is required to start VM.")
    memory_req_fulfilled_after_overcommit: bool = Field(
        description="Memory requirements of VM are fulfilled if over-committing memory is specified.",
    )
    arc_to_shrink: int | None = Field(description="Size of ARC to shrink in bytes.")
    current_arc_max: int = Field(description="Current size of max ARC in bytes.")
    arc_min: int = Field(description="Minimum size of ARC in bytes.")
    arc_max_after_shrink: int = Field(description="Size of max ARC in bytes after shrinking.")
    actual_vm_requested_memory: int = Field(
        description=(
            "VM memory in bytes to consider when making calculations for available/required memory. If VM ballooning is"
            " specified for the VM, the minimum VM memory specified by user will be taken into account otherwise total "
            "VM memory requested will be taken into account."
        ),
    )


class VMGetVmMemoryInfoResult(BaseModel):
    result: VMGetVmMemoryInfo = Field(description="VM memory info.")


class VMRandomMacArgs(BaseModel):
    pass


class VMRandomMacResult(BaseModel):
    result: str = Field(description="Randomly generated MAC address suitable for virtual machine network interfaces.")


class VMGuestNetworkInterfaceIPAddress(BaseModel):
    ip_address: IPvAnyAddress = Field(description="IP address assigned to the interface.")
    prefix: int = Field(description="Prefix length (subnet mask bits).")
    ip_address_type: Literal["IPV4", "IPV6"] = Field(description="Address family: 'IPV4' or 'IPV6'.")


class VMGuestNetworkInterface(BaseModel):
    name: str = Field(description="Interface name as seen in the guest OS (e.g. 'eth0', 'ens3').")
    hardware_address: str = Field(description="MAC address of the interface.")
    ip_addresses: list[VMGuestNetworkInterfaceIPAddress] = Field(
        description="IP addresses currently assigned to this interface."
    )


class VMGetGuestNetworkInterfacesArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine.")


class VMGetGuestNetworkInterfacesResult(BaseModel):
    result: list[VMGuestNetworkInterface] = Field(
        description="Network interfaces reported by the QEMU guest agent."
    )
