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
    state: NonEmptyString = Field(
        examples=["RUNNING", "STOPPED", "SUSPENDED"],
        description="Current state of the virtual machine.",
    )
    pid: int | None = Field(description="Process ID of the running VM. `null` if not running.")
    domain_state: NonEmptyString = Field(description="Hypervisor-specific domain state.")


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
    vcpus: int = Field(ge=1, default=1, description="Number of virtual CPUs allocated to the VM.")
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
    suspend_on_snapshot: bool = Field(default=False, description="Whether to suspend the VM when taking snapshots.")
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
        description="Whether to hide hypervisor signatures from guest OS MSR access.",
    )
    ensure_display_device: bool = Field(
        default=True,
        description="Whether to ensure at least one display device is configured for the VM.",
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
    uuid: str | None = Field(default=None, description="Unique UUID for the VM. `null` to auto-generate.")
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
    bootloader_ovmf: str | None = Field(
        default=None,
        examples=['OVMF_CODE.fd', 'OVMF_CODE.secboot.fd'],
        description="OVMF firmware file to use for UEFI boot.",
    )

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
    result: bool = Field(description="Whether the virtual machine was successfully deleted.")


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
    UEFI: Literal['UEFI'] = Field(default='UEFI', description="Modern UEFI firmware with secure boot support.")
    UEFI_CSM: Literal['Legacy BIOS'] = Field(
        default='Legacy BIOS',
        description="UEFI with Compatibility Support Module for legacy BIOS compatibility.",
    )


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


@single_argument_result
class VMGuestArchitectureAndMachineChoicesResult(BaseModel):
    model_config = ConfigDict(extra='allow')


class VMCloneArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to clone.")
    name: NonEmptyString | None = Field(
        default=None,
        description="Name for the cloned virtual machine. `null` to auto-generate.",
    )


class VMCloneResult(BaseModel):
    result: bool = Field(description="Whether the virtual machine was successfully cloned.")


@single_argument_args('vm_import_disk_image')
class VMImportDiskImageArgs(BaseModel):
    diskimg: NonEmptyString = Field(description="Path to the disk image file to import.")
    zvol: NonEmptyString = Field(description="Target ZFS volume path where the disk image will be imported.")


class VMImportDiskImageResult(BaseModel):
    result: bool = Field(description="Whether the disk image import operation was successful.")


@single_argument_args('vm_export_disk_image')
class VMExportDiskImageArgs(BaseModel):
    format: NonEmptyString = Field(description="Output format for the exported disk image (e.g., 'qcow2', 'raw').")
    directory: NonEmptyString = Field(description="Directory path where the exported disk image will be saved.")
    zvol: NonEmptyString = Field(description="Source ZFS volume to export as a disk image.")


class VMExportDiskImageResult(BaseModel):
    result: bool = Field(description="Whether the disk image export operation was successful.")


class VMSupportsVirtualizationArgs(BaseModel):
    pass


class VMSupportsVirtualizationResult(BaseModel):
    result: bool = Field(description="Whether the host system supports hardware virtualization (VT-x/AMD-V).")


class VMVirtualizationDetailsArgs(BaseModel):
    pass


@single_argument_result
class VMVirtualizationDetailsResult(BaseModel):
    supported: bool = Field(description="Whether hardware virtualization is supported and available.")
    error: str | None = Field(description="Error message if virtualization is not available. `null` if supported.")


class VMMaximumSupportedVcpusArgs(BaseModel):
    pass


class VMMaximumSupportedVcpusResult(BaseModel):
    result: int = Field(description="Maximum number of virtual CPUs supported by the host system.")


class VMFlagsArgs(BaseModel):
    pass


@single_argument_result
class VMFlagsResult(BaseModel):
    intel_vmx: bool = Field(description="Whether Intel VT-x (VMX) virtualization is available.")
    unrestricted_guest: bool = Field(description="Whether Intel unrestricted guest mode is supported.")
    amd_rvi: bool = Field(description="Whether AMD Rapid Virtualization Indexing (RVI/NPT) is available.")
    amd_asids: bool = Field(description="Whether AMD Address Space Identifiers (ASIDs) are supported.")


class VMGetConsoleArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get console connection information for.")


class VMGetConsoleResult(BaseModel):
    result: NonEmptyString = Field(description="Console connection string or command for accessing the VM console.")


class VMCpuModelChoicesArgs(BaseModel):
    pass


@single_argument_result
class VMCpuModelChoicesResult(BaseModel):
    """Available CPU models for virtual machine emulation."""
    model_config = ConfigDict(extra='allow')


class VMGetMemoryUsageArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get memory usage for.")


class VMGetMemoryUsageResult(BaseModel):
    result: int = Field(description="Current memory usage of the virtual machine in bytes.")


class VMPortWizardArgs(BaseModel):
    pass


@single_argument_result
class VMPortWizardResult(BaseModel):
    port: int = Field(description="Available server port")
    web: int = Field(description="Web port to be used based on available port")


class VMResolutionChoicesArgs(BaseModel):
    pass


class VMResolutionChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Object of available display resolutions for virtual machines.")


class VMGetDisplayDevicesArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get display devices for.")


class GetDisplayDevice(VMDisplayDevice):
    password_configured: bool = Field(description="Whether a password has been configured for display access.")


class DisplayDevice(VMDeviceEntry):
    attributes: GetDisplayDevice = Field(
        description="Display device attributes including password configuration status.",
    )


class VMGetDisplayDevicesResult(BaseModel):
    result: list[DisplayDevice] = Field(description="Array of display devices configured for the virtual machine.")


class DisplayWebURIOptions(BaseModel):
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
    options: DisplayWebURIOptions = Field(
        default=DisplayWebURIOptions(),
        description="Options for generating the web display URI.",
    )


@single_argument_result
class VMGetDisplayWebUriResult(BaseModel):
    error: str | None = Field(description="Error message if URI generation failed. `null` on success.")
    uri: str | None = Field(description="Generated web URI for accessing the VM display. `null` on error.")


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


@single_argument_result
class VMGetVmemoryInUseResult(BaseModel):
    RNP: int = Field(description="Running but not provisioned, in bytes")
    PRD: int = Field(description="Provisioned but not running, in bytes")
    RPRD: int = Field(description="Running and provisioned, in bytes")


class VMGetAvailableMemoryArgs(BaseModel):
    overcommit: bool = Field(
        default=False,
        description="Whether to include overcommitted memory in available memory calculation.",
    )


class VMGetAvailableMemoryResult(BaseModel):
    result: int = Field(description="Available memory for virtual machines in bytes.")


class VMGetVmMemoryInfoArgs(BaseModel):
    id: int = Field(description="ID of the virtual machine to get memory information for.")


@single_argument_result
class VMGetVmMemoryInfoResult(BaseModel):
    minimum_memory_requested: int | None = Field(description="Minimum memory requested by the VM")
    total_memory_requested: int = Field(description="Maximum / total memory requested by the VM")
    overcommit_required: bool = Field(description="Overcommit of memory is required to start VM")
    memory_req_fulfilled_after_overcommit: bool = Field(
        description="Memory requirements of VM are fulfilled if over-committing memory is specified",
    )
    arc_to_shrink: int | None = Field(description="Size of ARC to shrink in bytes")
    current_arc_max: int = Field(description="Current size of max ARC in bytes")
    arc_min: int = Field(description="Minimum size of ARC in bytes")
    arc_max_after_shrink: int = Field(description="Size of max ARC in bytes after shrinking")
    actual_vm_requested_memory: int = Field(
        description=(
            "VM memory in bytes to consider when making calculations for available/required memory. If VM ballooning is"
            " specified for the VM, the minimum VM memory specified by user will be taken into account otherwise total "
            "VM memory requested will be taken into account."
        ),
    )


class VMRandomMacArgs(BaseModel):
    pass


class VMRandomMacResult(BaseModel):
    result: str = Field(description="Randomly generated MAC address suitable for virtual machine network interfaces.")
