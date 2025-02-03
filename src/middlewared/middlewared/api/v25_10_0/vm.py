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
    'VMBootloaderOVMFChoicesArgs', 'VMBootloaderOVMFChoicesResult', 'VMBootloaderOptionsArgs',
    'VMBootloaderOptionsResult', 'VMStatusArgs', 'VMStatusResult', 'VMLogFilePathArgs', 'VMLogFilePathResult',
    'VMLogFileDownloadArgs', 'VMLogFileDownloadResult', 'VMGuestArchitectureMachineChoicesArgs',
    'VMGuestArchitectureMachineChoicesResult', 'VMCloneArgs', 'VMCloneResult', 'VMImportDiskImageArgs',
    'VMImportDiskImageResult', 'VMExportDiskImageArgs', 'VMExportDiskImageResult', 'VMSupportsVirtualizationArgs',
    'VMSupportsVirtualizationResult', 'VMVirtualizationDetailsArgs', 'VMVirtualizationDetailsResult',
    'VMMaximumSupportedVCPUsArgs', 'VMMaximumSupportedVCPUsResult', 'VMFlagsArgs', 'VMFlagsResult', 'VMGetConsoleArgs',
    'VMGetConsoleResult', 'VMCPUModelChoicesArgs', 'VMCPUModelChoicesResult', 'VMGetMemoryUsageArgs',
    'VMGetMemoryUsageResult', 'VMPortWizardArgs', 'VMPortWizardResult', 'VMResolutionChoicesArgs',
    'VMResolutionChoicesResult', 'VMGetDisplayDevicesArgs', 'VMGetDisplayDevicesResult', 'VMDisplayWebURIArgs',
    'VMDisplayWebURIResult', 'VMStartArgs', 'VMStartResult', 'VMStopArgs', 'VMStopResult', 'VMRestartArgs',
    'VMRestartResult', 'VMResumeArgs', 'VMResumeResult', 'VMPoweroffArgs', 'VMPoweroffResult', 'VMSuspendArgs',
    'VMSuspendResult', 'VMGetVMemoryInUseArgs', 'VMGetVMemoryInUseResult', 'VMGetAvailableMemoryArgs',
    'VMGetAvailableMemoryResult', 'VMGetVMMemoryInfoArgs', 'VMGetVMMemoryInfoResult', 'VMRandomMacArgs',
    'VMRandomMacResult',
]


class VMStatus(BaseModel):
    state: NonEmptyString
    pid: int | None
    domain_state: NonEmptyString


class VMEntry(BaseModel):
    command_line_args: str = ''
    cpu_mode: Literal['CUSTOM', 'HOST-MODEL', 'HOST-PASSTHROUGH'] = 'CUSTOM'
    cpu_model: str | None = None
    name: NonEmptyString
    description: str = ''
    vcpus: int = Field(ge=1, default=1)
    cores: int = Field(ge=1, default=1)
    threads: int = Field(ge=1, default=1)
    cpuset: str | None = None  # TODO: Add validation for numeric set
    nodeset: str | None = None  # TODO: Same as above
    enable_cpu_topology_extension: bool = False
    pin_vcpus: bool = False
    suspend_on_snapshot: bool = False
    trusted_platform_module: bool = False
    memory: int = Field(ge=20)
    min_memory: int | None = Field(ge=20, default=None)
    hyperv_enlightenments: bool = False
    bootloader: Literal['UEFI_CSM', 'UEFI'] = 'UEFI'
    bootloader_ovmf: str = 'OVMF_CODE.fd'
    autostart: bool = True
    hide_from_msr: bool = False
    ensure_display_device: bool = True
    time: Literal['LOCAL', 'UTC'] = 'LOCAL'
    shutdown_timeout: int = Field(ge=5, le=300, default=90)
    arch_type: str | None = None
    machine_type: str | None = None
    uuid: str | None = None
    devices: list[VMDeviceEntry]
    display_available: bool
    id: int
    status: VMStatus


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


class VMBootloaderOVMFChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMBootloaderOVMFChoicesResult(BaseModel):
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


class VMGuestArchitectureMachineChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMGuestArchitectureMachineChoicesResult(BaseModel):
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


class VMMaximumSupportedVCPUsArgs(BaseModel):
    pass


class VMMaximumSupportedVCPUsResult(BaseModel):
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


class VMCPUModelChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMCPUModelChoicesResult(BaseModel):
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
    '''Available server port'''
    web: int
    '''Web port to be used based on available port'''


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


class VMDisplayWebURIArgs(BaseModel):
    id: int
    host: str = ''
    options: DisplayWebURIOptions = DisplayWebURIOptions()


@single_argument_result
class VMDisplayWebURIResult(BaseModel):
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


class VMGetVMemoryInUseArgs(BaseModel):
    pass


@single_argument_result
class VMGetVMemoryInUseResult(BaseModel):
    RNP: int
    '''Running but not provisioned'''
    PRD: int
    '''Provisioned but not running'''
    RPRD: int
    '''Running and provisioned'''


class VMGetAvailableMemoryArgs(BaseModel):
    overcommit: bool = False


class VMGetAvailableMemoryResult(BaseModel):
    result: int


class VMGetVMMemoryInfoArgs(BaseModel):
    id: int


@single_argument_result
class VMGetVMMemoryInfoResult(BaseModel):
    minimum_memory_requested: int | None
    '''Minimum memory requested by the VM'''
    total_memory_requested: int
    '''Maximum / total memory requested by the VM'''
    overcommit_required: bool
    '''Overcommit of memory is required to start VM'''
    memory_req_fulfilled_after_overcommit: bool
    '''Memory requirements of VM are fulfilled if over-committing memory is specified'''
    arc_to_shrink: int | None
    '''Size of ARC to shrink in bytes'''
    current_arc_max: int
    '''Current size of max ARC in bytes'''
    arc_min: int
    '''Minimum size of ARC in bytes'''
    arc_max_after_shrink: int
    '''Size of max ARC in bytes after shrinking'''
    actual_vm_requested_memory: int
    '''
    VM memory in bytes to consider when making calculations for available/required memory. If VM ballooning is
    specified for the VM, the minimum VM memory specified by user will be taken into account otherwise total VM
    memory requested will be taken into account.
    '''


class VMRandomMacArgs(BaseModel):
    pass


class VMRandomMacResult(BaseModel):
    result: str
