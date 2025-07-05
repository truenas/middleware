from typing import Literal

from pydantic import Field, PositiveInt

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args, UUIDv4String,
)


__all__ = [
    "ContainerEntry",
    "ContainerCreateArgs", "ContainerCreateResult",
    "ContainerUpdateArgs", "ContainerUpdateResult",
    "ContainerDeleteArgs", "ContainerDeleteResult",
    "ContainerStartArgs", "ContainerStartResult",
    "ContainerStopArgs", "ContainerStopResult",
    "ContainerMigrateArgs", "ContainerMigrateResult",
]


class IdmapConfigurationItem(BaseModel):
    target: PositiveInt
    """UID/GID 0 in container will be mapped to this target UID/GID in host."""
    count: PositiveInt
    """How many users/groups in container are allowed to map to host"s user/group."""


class IdmapConfiguration(BaseModel):
    uid: IdmapConfigurationItem
    """UID mapping configuration."""
    gid: IdmapConfigurationItem
    """GID mapping configuration."""


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
    vcpus: int | None = Field(ge=1, default=None)
    """How many CPUs container can use."""
    cores: int | None = Field(ge=1, default=None)
    """How many cores does each CPU have."""
    threads: int | None = Field(ge=1, default=None)
    """How many threads does each CPU core have."""
    cpuset: str | None = None  # TODO: Add validation for numeric set
    """List of physical CPU numbers that domain process and virtual CPUs can be pinned to by default."""
    memory: int | None = Field(ge=20, default=None)
    """Memory available to container (in megabytes)."""
    autostart: bool = True
    """Automatically start the container on boot."""
    time: Literal["LOCAL", "UTC"] = "LOCAL"
    """Whether container time should be local time or UTC time."""
    shutdown_timeout: int = Field(ge=5, le=300, default=90)
    """How many seconds to wait for container to shut down before killing it."""
    dataset: str
    """Which dataset to use as the container root filesystem."""
    init: str
    """"init" process commandline."""
    initdir: str | None = None
    """"init" process working dir."""
    initenv: dict[str, str] = {}
    """"init" process environment variables."""
    inituser: str | None = None
    """"init" process username."""
    initgroup: str | None = None
    """"init" process group."""
    idmap: IdmapConfiguration | None = None
    """ID mapping configuration."""
    capabilities_policy: Literal["DEFAULT", "ALLOW", "DENY"] = "DEFAULT"
    """Default rules for capabilities: either keep the default behavior that is dropping a few selected capabilities,
    or keep all capabilities or drop all capabilities. """
    capabilities_state: dict[str, bool] = {}
    """Enable or disable specific capabilities."""
    status: ContainerStatus
    """Container state."""


class ContainerCreate(ContainerEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    status: Excluded = excluded_field()
    pool: str
    "Pool to use for this container."
    image: "ContainerCreateImage"
    "Image to use for container creation."


class ContainerCreateImage(BaseModel):
    name: str
    "Image name. Use `container.image.query_registry` to list all available images."
    version: str
    "Image version. Use `container.image.query_registry` to list all available images."


@single_argument_args("container_create")
class ContainerCreateArgs(ContainerCreate):
    pass


class ContainerCreateResult(BaseModel):
    result: ContainerEntry
    """Newly created container."""


class ContainerUpdate(ContainerCreate, metaclass=ForUpdateMetaclass):
    pool: Excluded = excluded_field()
    image: Excluded = excluded_field()


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
