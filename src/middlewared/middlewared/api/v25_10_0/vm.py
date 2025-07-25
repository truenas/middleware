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
    """Whether to pin virtual CPUs to specific host CPU cores."""
    suspend_on_snapshot: bool = False
    """Whether to suspend the VM when taking snapshots."""
    trusted_platform_module: bool = False
    """Whether to enable virtual Trusted Platform Module (TPM) for the VM."""
    memory: int = Field(ge=20)
    """Amount of memory allocated to the VM in megabytes."""
    min_memory: int | None = Field(ge=20, default=None)
    """Minimum memory allocation for dynamic memory ballooning in megabytes. `null` to disable."""
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
    """Maximum time in seconds to wait for graceful shutdown before forcing power off."""
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
    status: VMStatus
    """Current runtime status information for the VM."""
    enable_secure_boot: bool = False
    """Whether to enable UEFI Secure Boot for enhanced security."""


class VMCreate(VMEntry):
    status: Excluded = excluded_field()
    id: Excluded = excluded_field()
    display_available: Excluded = excluded_field()
    devices: Excluded = excluded_field()

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


class VMUpdate(VMCreate, metaclass=ForUpdateMetaclass):
    pass


class VMUpdateArgs(BaseModel):
    id: int
    vm_update: VMUpdate


class VMUpdateResult(BaseModel):
    result: VMEntry


class VMDeleteOptions(BaseModel):
    zvols: bool = False
    force: bool = False


class VMDeleteArgs(BaseModel):
    id: int
    options: VMDeleteOptions = VMDeleteOptions()


class VMDeleteResult(BaseModel):
    result: bool


class VMBootloaderOvmfChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMBootloaderOvmfChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMBootloaderOptionsArgs(BaseModel):
    pass


@single_argument_result
class VMBootloaderOptionsResult(BaseModel):
    UEFI: Literal['UEFI'] = 'UEFI'
    UEFI_CSM: Literal['Legacy BIOS'] = 'Legacy BIOS'


class VMStatusArgs(BaseModel):
    id: int


class VMStatusResult(BaseModel):
    result: VMStatus


class VMLogFilePathArgs(BaseModel):
    id: int


class VMLogFilePathResult(BaseModel):
    result: NonEmptyString | None


class VMLogFileDownloadArgs(BaseModel):
    id: int


class VMLogFileDownloadResult(BaseModel):
    result: None


class VMGuestArchitectureAndMachineChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMGuestArchitectureAndMachineChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMCloneArgs(BaseModel):
    id: int
    name: NonEmptyString | None = None


class VMCloneResult(BaseModel):
    result: bool


@single_argument_args('vm_import_disk_image')
class VMImportDiskImageArgs(BaseModel):
    diskimg: NonEmptyString
    zvol: NonEmptyString


class VMImportDiskImageResult(BaseModel):
    result: bool


@single_argument_args('vm_export_disk_image')
class VMExportDiskImageArgs(BaseModel):
    format: NonEmptyString
    directory: NonEmptyString
    zvol: NonEmptyString


class VMExportDiskImageResult(BaseModel):
    result: bool


class VMSupportsVirtualizationArgs(BaseModel):
    pass


class VMSupportsVirtualizationResult(BaseModel):
    result: bool


class VMVirtualizationDetailsArgs(BaseModel):
    pass


@single_argument_result
class VMVirtualizationDetailsResult(BaseModel):
    supported: bool
    error: str | None


class VMMaximumSupportedVcpusArgs(BaseModel):
    pass


class VMMaximumSupportedVcpusResult(BaseModel):
    result: int


class VMFlagsArgs(BaseModel):
    pass


@single_argument_result
class VMFlagsResult(BaseModel):
    intel_vmx: bool
    unrestricted_guest: bool
    amd_rvi: bool
    amd_asids: bool


class VMGetConsoleArgs(BaseModel):
    id: int


class VMGetConsoleResult(BaseModel):
    result: NonEmptyString


class VMCpuModelChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMCpuModelChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMGetMemoryUsageArgs(BaseModel):
    id: int


class VMGetMemoryUsageResult(BaseModel):
    result: int


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


class VMGetDisplayDevicesArgs(BaseModel):
    id: int


class GetDisplayDevice(VMDisplayDevice):
    password_configured: bool


class DisplayDevice(VMDeviceEntry):
    attributes: GetDisplayDevice


class VMGetDisplayDevicesResult(BaseModel):
    result: list[DisplayDevice]


class DisplayWebURIOptions(BaseModel):
    protocol: Literal['HTTP', 'HTTPS'] = 'HTTP'


class VMGetDisplayWebUriArgs(BaseModel):
    id: int
    host: str = ''
    options: DisplayWebURIOptions = DisplayWebURIOptions()


@single_argument_result
class VMGetDisplayWebUriResult(BaseModel):
    error: str | None
    uri: str | None


class VMStartOptions(BaseModel):
    overcommit: bool = False


class VMStartArgs(BaseModel):
    id: int
    options: VMStartOptions = VMStartOptions()


class VMStartResult(BaseModel):
    result: None


class VMStopOptions(BaseModel):
    force: bool = False
    force_after_timeout: bool = False


class VMStopArgs(BaseModel):
    id: int
    options: VMStopOptions = VMStopOptions()


class VMStopResult(BaseModel):
    result: None


class VMPoweroffArgs(BaseModel):
    id: int


class VMPoweroffResult(BaseModel):
    result: None


class VMRestartArgs(BaseModel):
    id: int


class VMRestartResult(BaseModel):
    result: None


class VMSuspendArgs(BaseModel):
    id: int


class VMSuspendResult(BaseModel):
    result: None


class VMResumeArgs(BaseModel):
    id: int


class VMResumeResult(BaseModel):
    result: None


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


class VMGetAvailableMemoryResult(BaseModel):
    result: int


class VMGetVmMemoryInfoArgs(BaseModel):
    id: int


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
