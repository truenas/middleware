from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, PositiveInt

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args, UUIDv4String,
)

from .container_device import ContainerDeviceEntry


__all__ = [
    "ContainerEntry",
    "ContainerCreateArgs", "ContainerCreateResult",
    "ContainerUpdateArgs", "ContainerUpdateResult",
    "ContainerDeleteArgs", "ContainerDeleteResult",
    "ContainerPoolChoicesArgs", "ContainerPoolChoicesResult",
    "ContainerStartArgs", "ContainerStartResult",
    "ContainerStopArgs", "ContainerStopResult",
    "ContainerMigrateArgs", "ContainerMigrateResult",
    "ContainersMetricsEventSourceArgs", "ContainersMetricsEventSourceEvent"
]


class DefaultIdmapConfiguration(BaseModel):
    type: Literal["DEFAULT"]
    """Configuration type for default ID mapping."""


class IsolatedIdmapConfiguration(BaseModel):
    type: Literal["ISOLATED"]
    """Configuration type for isolated ID mapping."""
    slice: PositiveInt | None = Field(lt=1000)
    """`null` when creating means we'll look up an unused slice on backend."""


IdmapConfiguration = Annotated[
    Union[
        DefaultIdmapConfiguration,
        IsolatedIdmapConfiguration,
    ],
    Discriminator("type"),
]


class ContainerStatus(BaseModel):
    state: Literal["RUNNING", "STOPPED"]
    """Container state."""
    pid: int | None
    """Container PID (if running)."""
    domain_state: NonEmptyString | None
    """Domain state reported by libvirt."""


class ContainerEntry(BaseModel):
    id: int
    """Container ID."""
    uuid: UUIDv4String | None = None
    """Container UUID (for libvirt)."""
    name: NonEmptyString
    """Container name."""
    description: str = ""
    """Container description."""
    devices: list[ContainerDeviceEntry] = []
    """Container's devices."""
    cpuset: str | None = None
    """List of physical CPU numbers that domain process and virtual CPUs can be pinned to by default."""
    autostart: bool = True
    """Automatically start the container on boot."""
    time: Literal["LOCAL", "UTC"] = "LOCAL"
    """Whether container time should be local time or UTC time."""
    shutdown_timeout: int = Field(ge=5, le=300, default=90)
    """How many seconds to wait for container to shut down before killing it."""
    dataset: str
    """Which dataset to use as the container root filesystem."""
    init: str = '/sbin/init'
    """"init" process commandline."""
    initdir: str | None = None
    """"init" process working dir."""
    initenv: dict[str, str] = {}
    """"init" process environment variables."""
    inituser: str | None = None
    """"init" process username."""
    initgroup: str | None = None
    """"init" process group."""
    idmap: IdmapConfiguration | None = DefaultIdmapConfiguration(type="DEFAULT")
    """Idmap configuration for the container\
    \
    There are three two possible values:\
    \
    DEFAULT: This applies the standard TrueNAS idmap namespace configuration.\
    It changes user ID (UID) 0 (root) in the container to UID 2147000001 (truenas_container_unpriv_root).\
    It offsets the other container UIDs by the same amount.\
    For example, UID 1000 in the container becomes UID 2147001001 in the host.\
    \
    ISOLATED: Same as `DEFAULT`, but UID will be calculated as `2147000001 + 65536 * slice`.\
    This will ensure unique ID for each container (provided that the `slice` is also unique).
    \
    None: The container does not apply any idmap namespace.\
    Container UIDs map directly to host UIDs.\
    For example, UID 0 in the container is UID 0 in the host.\
    \
    WARNING: For security, use the DEFAULT value. Security best practice is to run containers with idmap namespaces."""
    capabilities_policy: Literal["DEFAULT", "ALLOW", "DENY"] = "DEFAULT"
    """Default rules for capabilities: either keep the default behavior that is dropping the following capabilities:\
    sys_module, sys_time, mknod, audit_control, mac_admin. Or keep all capabilities, or drop all capabilities."""
    capabilities_state: dict[str, bool] = {}
    """Enable or disable specific capabilities."""
    status: ContainerStatus
    """Container state."""


class ContainerCreate(ContainerEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    status: Excluded = excluded_field()
    devices: Excluded = excluded_field()
    pool: str | None = None
    """Pool to use for this container. Leave it null to use container preferred pool instead."""
    image: "ContainerCreateImage"
    """Image to use for container creation."""


class ContainerCreateImage(BaseModel):
    name: str
    """Image name. Use `container.image.query_registry` to list all available images."""
    version: str
    """Image version. Use `container.image.query_registry` to list all available images."""


@single_argument_args("container_create")
class ContainerCreateArgs(ContainerCreate):
    pass


class ContainerCreateResult(BaseModel):
    result: ContainerEntry
    """Newly created container."""


class ContainerUpdate(ContainerCreate, metaclass=ForUpdateMetaclass):
    pool: Excluded = excluded_field()
    image: Excluded = excluded_field()
    idmap: Excluded = excluded_field()


class ContainerUpdateArgs(BaseModel):
    id: int
    """Container ID."""
    container_update: ContainerUpdate
    """New container parameters."""


class ContainerUpdateResult(BaseModel):
    result: ContainerEntry
    """Updated container."""


class ContainerDeleteArgs(BaseModel):
    id: int
    """Container ID."""


class ContainerDeleteResult(BaseModel):
    result: None


class ContainerPoolChoicesArgs(BaseModel):
    pass


class ContainerPoolChoicesResult(BaseModel):
    result: dict
    """Object of available ZFS pools that can be used for container root filesystem."""


class ContainerStartArgs(BaseModel):
    id: int
    """Container ID."""


class ContainerStartResult(BaseModel):
    result: None


class ContainerStopOptions(BaseModel):
    force: bool = False
    """Kill the container."""
    force_after_timeout: bool = False
    """Kill the container if it does not stop within the `shutdown_timeout`."""


class ContainerStopArgs(BaseModel):
    id: int
    """Container ID."""
    options: ContainerStopOptions = ContainerStopOptions()
    """Container stop options."""


class ContainerStopResult(BaseModel):
    result: None


class ContainerMigrateArgs(BaseModel):
    pass


class ContainerMigrateResult(BaseModel):
    result: None


class ContainersMetricsEventSourceArgs(BaseModel):
    interval: int = Field(default=2, ge=2)
    """Interval in seconds between metrics updates (minimum 2 seconds)."""


class ContainersMetricsEventSourceEvent(BaseModel):
    result: dict[str, dict] = Field(examples=[{
        "15": {
            "cpu": {
                "cpu_user_percentage": 0.0,
                "cpu_system_percentage": 0.0
            },
            "throttled": {
                "throttled_throttled_percentage": 0.0
            },
            "throttled_duration": {
                "throttled_duration_duration_ms": 0.0
            },
            "mem": {
                "mem_anon_mib": 9.5507812,
                "mem_kernel_stack_mib": 0.109375,
                "mem_slab_mib": 1.5317764,
                "mem_sock_mib": 0.0117188,
                "mem_anon_thp_mib": 2.0,
                "mem_file_mib": 15.8125
            },
            "writeback": {
                "writeback_dirty_mib": 0.0,
                "writeback_writeback_mib": 0.0
            },
            "pgfaults": {
                "pgfaults_pgfault_mib_s": 0.0,
                "pgfaults_pgmajfault_mib_s": 0.0
            },
            "mem_usage": {
                "mem_usage_ram_mib": 28.4375,
                "mem_usage_swap_mib": 0.0
            },
            "mem_usage_limit": {
                "mem_usage_limit_available_mib": 9693.0039062,
                "mem_usage_limit_used_mib": 28.4375
            },
            "mem_utilization": {
                "mem_utilization_utilization_percentage": 0.0
            },
            "io": {
                "io_read_kib_s": 0.0,
                "io_write_kib_s": 0.0
            },
            "serviced_ops": {
                "serviced_ops_read_operations_s": 0.0,
                "serviced_ops_write_operations_s": 0.0
            },
            "pids_current": {
                "pids_current_pids_pids": 12.0
            },
            "cpu_some_pressure": {
                "cpu_some_pressure_some_10_percentage": 0.0,
                "cpu_some_pressure_some_60_percentage": 0.0,
                "cpu_some_pressure_some_300_percentage": 0.0
            },
            "cpu_some_pressure_stall_time": {
                "cpu_some_pressure_stall_time_time_ms": 0.0
            },
            "cpu_full_pressure": {
                "cpu_full_pressure_full_10_percentage": 0.0,
                "cpu_full_pressure_full_60_percentage": 0.0,
                "cpu_full_pressure_full_300_percentage": 0.0
            },
            "cpu_full_pressure_stall_time": {
                "cpu_full_pressure_stall_time_time_ms": 0.0
            },
            "mem_some_pressure": {
                "mem_some_pressure_some_10_percentage": 0.0,
                "mem_some_pressure_some_60_percentage": 0.0,
                "mem_some_pressure_some_300_percentage": 0.0
            },
            "memory_some_pressure_stall_time": {
                "memory_some_pressure_stall_time_time_ms": 0.0
            },
            "mem_full_pressure": {
                "mem_full_pressure_full_10_percentage": 0.0,
                "mem_full_pressure_full_60_percentage": 0.0,
                "mem_full_pressure_full_300_percentage": 0.0
            },
            "memory_full_pressure_stall_time": {
                "memory_full_pressure_stall_time_time_ms": 0.0
            },
            "io_some_pressure": {
                "io_some_pressure_some_10_percentage": 0.0,
                "io_some_pressure_some_60_percentage": 0.0,
                "io_some_pressure_some_300_percentage": 0.0
            },
            "io_some_pressure_stall_time": {
                "io_some_pressure_stall_time_time_ms": 0.0
            },
            "io_full_pressure": {
                "io_full_pressure_full_10_percentage": 0.0,
                "io_full_pressure_full_60_percentage": 0.0,
                "io_full_pressure_full_300_percentage": 0.0
            },
            "io_full_pressure_stall_time": {
                "io_full_pressure_stall_time_time_ms": 0.0
            },
            "cpu_limit": {
                "cpu_limit_used_percentage": 0.0
            }
        }
    }])
    """Real-time metrics data for all virtual instances."""
