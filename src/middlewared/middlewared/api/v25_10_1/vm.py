import uuid

from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
    single_argument_result,
)

from .vm_device import VMDisplayDevice, VMDeviceEntry


__all__ = [
    'VMEntry', 'VMCreateArgs', 'VMCreateResult', 'VMUpdateArgs', 'VMUpdateResult', 'VMDeleteArgs', 'VMDeleteResult',
    'VMBootloaderOvmfChoicesArgs', 'VMBootloaderOvmfChoicesResult', 'VMBootloaderOptionsArgs',
    'VMBootloaderOptionsResult', 'VMStatusArgs', 'VMStatusResult', 'VMLogFilePathArgs', 'VMLogFilePathResult',
    'VMLogFileDownloadArgs', 'VMLogFileDownloadResult', 'VMGuestArchitectureAndMachineChoicesArgs',
    'VMGuestArchitectureAndMachineChoicesResult', 'VMCloneArgs', 'VMCloneResult', 'VMImportDiskImageArgs',
    'VMImportDiskImageResult', 'VMExportDiskImageArgs', 'VMExportDiskImageResult', 'VMSupportsVirtualizationArgs',
    'VMSupportsVirtualizationResult', 'VMVirtualizationDetailsArgs', 'VMVirtualizationDetailsResult',
    'VMMaximumSupportedVcpusArgs', 'VMMaximumSupportedVcpusResult', 'VMFlagsArgs', 'VMFlagsResult', 'VMGetConsoleArgs',
    'VMGetConsoleResult', 'VMCpuModelChoicesArgs', 'VMCpuModelChoicesResult', 'VMGetMemoryUsageArgs',
    'VMGetMemoryUsageResult', 'VMPortWizardArgs', 'VMPortWizardResult', 'VMResolutionChoicesArgs',
    'VMResolutionChoicesResult', 'VMGetDisplayDevicesArgs', 'VMGetDisplayDevicesResult', 'VMGetDisplayWebUriArgs',
    'VMGetDisplayWebUriResult', 'VMStartArgs', 'VMStartResult', 'VMStopArgs', 'VMStopResult', 'VMRestartArgs',
    'VMRestartResult', 'VMResumeArgs', 'VMResumeResult', 'VMPoweroffArgs', 'VMPoweroffResult', 'VMSuspendArgs',
    'VMSuspendResult', 'VMGetVmemoryInUseArgs', 'VMGetVmemoryInUseResult', 'VMGetAvailableMemoryArgs',
    'VMGetAvailableMemoryResult', 'VMGetVmMemoryInfoArgs', 'VMGetVmMemoryInfoResult', 'VMRandomMacArgs',
    'VMRandomMacResult',
]


class VMStatus(BaseModel):
    state: NonEmptyString = Field(examples=["RUNNING", "STOPPED", "SUSPENDED"])
    """Current state of the virtual machine."""
    pid: int | None
    """Process ID of the running VM. `null` if not running."""
    domain_state: NonEmptyString
    """Hypervisor-specific domain state."""


class VMEntry(BaseModel):
    command_line_args: str = ''
    """Additional command line arguments passed to the VM hypervisor."""
    cpu_mode: Literal['CUSTOM', 'HOST-MODEL', 'HOST-PASSTHROUGH'] = 'CUSTOM'
    """CPU virtualization mode.

    * `CUSTOM`: Use specified model.
    * `HOST-MODEL`: Mirror host CPU.
    * `HOST-PASSTHROUGH`: Provide direct access to host CPU features.

    """
    cpu_model: str | None = None
    """Specific CPU model to emulate. `null` to use hypervisor default."""
    name: NonEmptyString
    """Display name of the virtual machine."""
    description: str = ''
    """Optional description or notes about the virtual machine."""
    vcpus: int = Field(ge=1, default=1)
    """Number of virtual CPUs allocated to the VM."""
    cores: int = Field(ge=1, default=1)
    """Number of CPU cores per socket."""
    threads: int = Field(ge=1, default=1)
    """Number of threads per CPU core."""
    cpuset: str | None = None  # TODO: Add validation for numeric set
    """Set of host CPU cores to pin VM CPUs to. `null` for no pinning."""
    nodeset: str | None = None  # TODO: Same as above
    """Set of NUMA nodes to constrain VM memory allocation. `null` for no constraints."""
    enable_cpu_topology_extension: bool = False
    """Whether to expose detailed CPU topology information to the guest OS."""
    pin_vcpus: bool = False
    """Whether to pin virtual CPUs to specific host CPU cores. Improves performance but reduces host flexibility."""
    suspend_on_snapshot: bool = False
    """Whether to suspend the VM when taking snapshots."""
    trusted_platform_module: bool = False
    """Whether to enable virtual Trusted Platform Module (TPM) for the VM."""
    memory: int = Field(ge=20)
    """Amount of memory allocated to the VM in megabytes."""
    min_memory: int | None = Field(ge=20, default=None)
    """Minimum memory allocation for dynamic memory ballooning in megabytes. Allows VM memory to shrink \
    during low usage but guarantees this minimum. `null` to disable ballooning."""
    hyperv_enlightenments: bool = False
    """Whether to enable Hyper-V enlightenments for improved Windows guest performance."""
    bootloader: Literal['UEFI_CSM', 'UEFI'] = 'UEFI'
    """Boot firmware type. `UEFI` for modern UEFI, `UEFI_CSM` for legacy BIOS compatibility."""
    bootloader_ovmf: str = Field(default='OVMF_CODE.fd', examples=['OVMF_CODE.fd', 'OVMF_CODE.secboot.fd'])
    """OVMF firmware file to use for UEFI boot."""
    autostart: bool = True
    """Whether to automatically start the VM when the host system boots."""
    hide_from_msr: bool = False
    """Whether to hide hypervisor signatures from guest OS MSR access."""
    ensure_display_device: bool = True
    """Whether to ensure at least one display device is configured for the VM."""
    time: Literal['LOCAL', 'UTC'] = 'LOCAL'
    """Guest OS time zone reference. `LOCAL` uses host timezone, `UTC` uses coordinated universal time."""
    shutdown_timeout: int = Field(ge=5, le=300, default=90)
    """Maximum time in seconds to wait for graceful shutdown before forcing power off. Default 90s balances \
    allowing sufficient time for clean shutdown while avoiding indefinite hangs."""
    arch_type: str | None = None
    """Guest architecture type. `null` to use hypervisor default."""
    machine_type: str | None = None
    """Virtual machine type/chipset. `null` to use hypervisor default."""
    uuid: str | None = None
    """Unique UUID for the VM. `null` to auto-generate."""
    devices: list[VMDeviceEntry]
    """Array of virtual devices attached to this VM."""
    display_available: bool
    """Whether at least one display device is available for this VM."""
    id: int
    """Unique identifier for the virtual machine."""
    status: VMStatus
    """Current runtime status information for the VM."""
    enable_secure_boot: bool = False
    """Whether to enable UEFI Secure Boot for enhanced security."""


class VMCreate(VMEntry):
    status: Excluded = excluded_field()
    id: Excluded = excluded_field()
    display_available: Excluded = excluded_field()
    devices: Excluded = excluded_field()
    bootloader_ovmf: str | None = Field(default=None, examples=['OVMF_CODE.fd', 'OVMF_CODE.secboot.fd'])
    """OVMF firmware file to use for UEFI boot."""

    @field_validator('uuid')
    def validate_uuid(cls, value):
        if value is not None:
            try:
                uuid.UUID(value, version=4)
            except ValueError:
                raise ValueError('UUID is not valid version 4')
        return value


@single_argument_args('vm_create')
class VMCreateArgs(VMCreate):
    pass


class VMCreateResult(BaseModel):
    result: VMEntry
    """The newly created virtual machine configuration."""


class VMUpdate(VMCreate, metaclass=ForUpdateMetaclass):
    bootloader_ovmf: Excluded = excluded_field()
    enable_secure_boot: Excluded = excluded_field()


class VMUpdateArgs(BaseModel):
    id: int
    """ID of the virtual machine to update."""
    vm_update: VMUpdate
    """Updated configuration for the virtual machine."""


class VMUpdateResult(BaseModel):
    result: VMEntry
    """The updated virtual machine configuration."""


class VMDeleteOptions(BaseModel):
    zvols: bool = False
    """Delete associated ZFS volumes when deleting the VM."""
    force: bool = False
    """Force deletion even if the VM is currently running."""


class VMDeleteArgs(BaseModel):
    id: int
    """ID of the virtual machine to delete."""
    options: VMDeleteOptions = VMDeleteOptions()
    """Options controlling the VM deletion process."""


class VMDeleteResult(BaseModel):
    result: bool
    """Whether the virtual machine was successfully deleted."""


class VMBootloaderOvmfChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMBootloaderOvmfChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    """Available OVMF firmware files for UEFI booting."""


class VMBootloaderOptionsArgs(BaseModel):
    pass


@single_argument_result
class VMBootloaderOptionsResult(BaseModel):
    UEFI: Literal['UEFI'] = 'UEFI'
    """Modern UEFI firmware with secure boot support."""
    UEFI_CSM: Literal['Legacy BIOS'] = 'Legacy BIOS'
    """UEFI with Compatibility Support Module for legacy BIOS compatibility."""


class VMStatusArgs(BaseModel):
    id: int
    """ID of the virtual machine to get status for."""


class VMStatusResult(BaseModel):
    result: VMStatus
    """Current status and runtime information for the virtual machine."""


class VMLogFilePathArgs(BaseModel):
    id: int
    """ID of the virtual machine to get log file path for."""


class VMLogFilePathResult(BaseModel):
    result: NonEmptyString | None
    """Path to the VM log file. `null` if no log file exists."""


class VMLogFileDownloadArgs(BaseModel):
    id: int
    """ID of the virtual machine to download log file for."""


class VMLogFileDownloadResult(BaseModel):
    result: None


class VMGuestArchitectureAndMachineChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMGuestArchitectureAndMachineChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMCloneArgs(BaseModel):
    id: int
    """ID of the virtual machine to clone."""
    name: NonEmptyString | None = None
    """Name for the cloned virtual machine. `null` to auto-generate."""


class VMCloneResult(BaseModel):
    result: bool
    """Whether the virtual machine was successfully cloned."""


@single_argument_args('vm_import_disk_image')
class VMImportDiskImageArgs(BaseModel):
    diskimg: NonEmptyString
    """Path to the disk image file to import."""
    zvol: NonEmptyString
    """Target ZFS volume path where the disk image will be imported."""


class VMImportDiskImageResult(BaseModel):
    result: bool
    """Whether the disk image import operation was successful."""


@single_argument_args('vm_export_disk_image')
class VMExportDiskImageArgs(BaseModel):
    format: NonEmptyString
    """Output format for the exported disk image (e.g., 'qcow2', 'raw')."""
    directory: NonEmptyString
    """Directory path where the exported disk image will be saved."""
    zvol: NonEmptyString
    """Source ZFS volume to export as a disk image."""


class VMExportDiskImageResult(BaseModel):
    result: bool
    """Whether the disk image export operation was successful."""


class VMSupportsVirtualizationArgs(BaseModel):
    pass


class VMSupportsVirtualizationResult(BaseModel):
    result: bool
    """Whether the host system supports hardware virtualization (VT-x/AMD-V)."""


class VMVirtualizationDetailsArgs(BaseModel):
    pass


@single_argument_result
class VMVirtualizationDetailsResult(BaseModel):
    supported: bool
    """Whether hardware virtualization is supported and available."""
    error: str | None
    """Error message if virtualization is not available. `null` if supported."""


class VMMaximumSupportedVcpusArgs(BaseModel):
    pass


class VMMaximumSupportedVcpusResult(BaseModel):
    result: int
    """Maximum number of virtual CPUs supported by the host system."""


class VMFlagsArgs(BaseModel):
    pass


@single_argument_result
class VMFlagsResult(BaseModel):
    intel_vmx: bool
    """Whether Intel VT-x (VMX) virtualization is available."""
    unrestricted_guest: bool
    """Whether Intel unrestricted guest mode is supported."""
    amd_rvi: bool
    """Whether AMD Rapid Virtualization Indexing (RVI/NPT) is available."""
    amd_asids: bool
    """Whether AMD Address Space Identifiers (ASIDs) are supported."""


class VMGetConsoleArgs(BaseModel):
    id: int
    """ID of the virtual machine to get console connection information for."""


class VMGetConsoleResult(BaseModel):
    result: NonEmptyString
    """Console connection string or command for accessing the VM console."""


class VMCpuModelChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMCpuModelChoicesResult(BaseModel):
    """Available CPU models for virtual machine emulation."""
    model_config = ConfigDict(extra='allow')


class VMGetMemoryUsageArgs(BaseModel):
    id: int
    """ID of the virtual machine to get memory usage for."""


class VMGetMemoryUsageResult(BaseModel):
    result: int
    """Current memory usage of the virtual machine in bytes."""


class VMPortWizardArgs(BaseModel):
    pass


@single_argument_result
class VMPortWizardResult(BaseModel):
    port: int
    """Available server port"""
    web: int
    """Web port to be used based on available port"""


class VMResolutionChoicesArgs(BaseModel):
    pass


class VMResolutionChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available display resolutions for virtual machines."""


class VMGetDisplayDevicesArgs(BaseModel):
    id: int
    """ID of the virtual machine to get display devices for."""


class GetDisplayDevice(VMDisplayDevice):
    password_configured: bool
    """Whether a password has been configured for display access."""


class DisplayDevice(VMDeviceEntry):
    attributes: GetDisplayDevice
    """Display device attributes including password configuration status."""


class VMGetDisplayDevicesResult(BaseModel):
    result: list[DisplayDevice]
    """Array of display devices configured for the virtual machine."""


class DisplayWebURIOptions(BaseModel):
    protocol: Literal['HTTP', 'HTTPS'] = 'HTTP'
    """Protocol to use for the web display URI (HTTP or HTTPS)."""


class VMGetDisplayWebUriArgs(BaseModel):
    id: int
    """ID of the virtual machine to get display web URI for."""
    host: str = ''
    """Hostname or IP address to use in the URI. Empty string for automatic detection."""
    options: DisplayWebURIOptions = DisplayWebURIOptions()
    """Options for generating the web display URI."""


@single_argument_result
class VMGetDisplayWebUriResult(BaseModel):
    error: str | None
    """Error message if URI generation failed. `null` on success."""
    uri: str | None
    """Generated web URI for accessing the VM display. `null` on error."""


class VMStartOptions(BaseModel):
    overcommit: bool = False
    """Whether to allow memory overcommitment when starting the VM."""


class VMStartArgs(BaseModel):
    id: int
    """ID of the virtual machine to start."""
    options: VMStartOptions = VMStartOptions()
    """Options controlling the VM start process."""


class VMStartResult(BaseModel):
    result: None
    """Returns `null` on successful VM start initiation."""


class VMStopOptions(BaseModel):
    force: bool = False
    """Whether to force immediate shutdown without graceful shutdown attempt."""
    force_after_timeout: bool = False
    """Whether to force shutdown if graceful shutdown times out."""


class VMStopArgs(BaseModel):
    id: int
    """ID of the virtual machine to stop."""
    options: VMStopOptions = VMStopOptions()
    """Options controlling the VM stop process."""


class VMStopResult(BaseModel):
    result: None
    """Returns `null` on successful VM stop initiation."""


class VMPoweroffArgs(BaseModel):
    id: int
    """ID of the virtual machine to power off forcefully."""


class VMPoweroffResult(BaseModel):
    result: None
    """Returns `null` on successful VM power off initiation."""


class VMRestartArgs(BaseModel):
    id: int
    """ID of the virtual machine to restart."""


class VMRestartResult(BaseModel):
    result: None
    """Returns `null` on successful VM restart initiation."""


class VMSuspendArgs(BaseModel):
    id: int
    """ID of the virtual machine to suspend."""


class VMSuspendResult(BaseModel):
    result: None
    """Returns `null` on successful VM suspend initiation."""


class VMResumeArgs(BaseModel):
    id: int
    """ID of the virtual machine to resume from suspended state."""


class VMResumeResult(BaseModel):
    result: None
    """Returns `null` on successful VM resume initiation."""


class VMGetVmemoryInUseArgs(BaseModel):
    pass


@single_argument_result
class VMGetVmemoryInUseResult(BaseModel):
    RNP: int
    """Running but not provisioned"""
    PRD: int
    """Provisioned but not running"""
    RPRD: int
    """Running and provisioned"""


class VMGetAvailableMemoryArgs(BaseModel):
    overcommit: bool = False
    """Whether to include overcommitted memory in available memory calculation."""


class VMGetAvailableMemoryResult(BaseModel):
    result: int
    """Available memory for virtual machines in megabytes."""


class VMGetVmMemoryInfoArgs(BaseModel):
    id: int
    """ID of the virtual machine to get memory information for."""


@single_argument_result
class VMGetVmMemoryInfoResult(BaseModel):
    minimum_memory_requested: int | None
    """Minimum memory requested by the VM"""
    total_memory_requested: int
    """Maximum / total memory requested by the VM"""
    overcommit_required: bool
    """Overcommit of memory is required to start VM"""
    memory_req_fulfilled_after_overcommit: bool
    """Memory requirements of VM are fulfilled if over-committing memory is specified"""
    arc_to_shrink: int | None
    """Size of ARC to shrink in bytes"""
    current_arc_max: int
    """Current size of max ARC in bytes"""
    arc_min: int
    """Minimum size of ARC in bytes"""
    arc_max_after_shrink: int
    """Size of max ARC in bytes after shrinking"""
    actual_vm_requested_memory: int
    """
    VM memory in bytes to consider when making calculations for available/required memory. If VM ballooning is \
    specified for the VM, the minimum VM memory specified by user will be taken into account otherwise total VM \
    memory requested will be taken into account.
    """


class VMRandomMacArgs(BaseModel):
    pass


class VMRandomMacResult(BaseModel):
    result: str
    """Randomly generated MAC address suitable for virtual machine network interfaces."""
