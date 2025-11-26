from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import IPvAnyInterface, Field, field_validator, model_validator, RootModel
from pydantic.json_schema import SkipJsonSchema

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, HttpUrl, NonEmptyString, single_argument_args,
)


__all__ = [
    'DockerEntry', 'DockerUpdateArgs', 'DockerUpdateResult', 'DockerStatusArgs', 'DockerStatusResult',
    'DockerNvidiaPresentArgs', 'DockerNvidiaPresentResult', 'DockerBackupArgs', 'DockerBackupResult',
    'DockerListBackupsArgs', 'DockerListBackupsResult', 'DockerRestoreBackupArgs', 'DockerRestoreBackupResult',
    'DockerDeleteBackupArgs', 'DockerDeleteBackupResult', 'DockerBackupToPoolArgs', 'DockerBackupToPoolResult',
    'DockerEventsAddedEvent', 'DockerStateChangedEvent',
]


class AddressPool(BaseModel):
    base: IPvAnyInterface
    """Base network address with prefix for the pool."""
    size: Annotated[int, Field(ge=1)]
    """Subnet size for networks allocated from this pool."""

    @field_validator('base')
    @classmethod
    def check_prefixlen(cls, v):
        if v.network.prefixlen in (32, 128):
            raise ValueError('Prefix length of base network cannot be 32 or 128.')
        return v

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.base.version == 4 and self.size > 32:
            raise ValueError('Size must be <= 32 for IPv4.')
        elif self.base.version == 6 and self.size > 128:
            raise ValueError('Size must be <= 128 for IPv6.')
        return self


class RegistryMirror(BaseModel):
    url: HttpUrl
    """URL of the registry mirror."""
    insecure: bool
    """Whether the registry mirror uses an insecure (HTTP) connection."""


class DockerEntry(BaseModel):
    id: int
    """Unique identifier for the Docker configuration."""
    enable_image_updates: bool
    """Whether automatic Docker image updates are enabled."""
    dataset: NonEmptyString | None
    """ZFS dataset used for Docker data storage or `null`."""
    pool: NonEmptyString | None
    """Storage pool used for Docker or `null` if not configured."""
    nvidia: SkipJsonSchema[bool]
    """Whether NVIDIA GPU support is enabled for containers."""
    address_pools: list[dict]
    """Array of network address pools for container networking."""
    cidr_v6: str
    """IPv6 CIDR block for Docker container networking."""
    registry_mirrors: list[RegistryMirror]
    """Array of registry mirrors."""

    @classmethod
    def from_previous(cls, value):
        value["registry_mirrors"] = [
            {"url": url, "insecure": True} for url in value.pop("insecure_registry_mirrors")
        ] + [
            {"url": url, "insecure": False} for url in value.pop("secure_registry_mirrors")
        ]
        return value

    @classmethod
    def to_previous(cls, value):
        registry_mirrors = value.pop("registry_mirrors")
        value["insecure_registry_mirrors"] = [m["url"] for m in registry_mirrors if m["insecure"]]
        value["secure_registry_mirrors"] = [m["url"] for m in registry_mirrors if not m["insecure"]]
        return value


@single_argument_args('docker_update')
class DockerUpdateArgs(DockerEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    address_pools: list[AddressPool]
    """Array of network address pools for container networking."""
    cidr_v6: IPvAnyInterface
    """IPv6 CIDR block for Docker container networking."""
    migrate_applications: bool
    """Whether to migrate existing applications when changing pools."""
    registry_mirrors: list[RegistryMirror]
    """Array of registry mirrors."""

    @field_validator('cidr_v6')
    @classmethod
    def validate_ipv6(cls, v):
        if v.version != 6:
            raise ValueError('cidr_v6 must be an IPv6 address.')
        if v.network.prefixlen == 128:
            raise ValueError('Prefix length of cidr_v6 network cannot be 128.')
        return v

    @field_validator('registry_mirrors')
    @classmethod
    def validate_registry_mirrors(cls, v):
        for mirror in v:
            if urlparse(mirror.url).scheme == 'http' and not mirror.insecure:
                raise ValueError(
                    f'Registry mirror URL that starts with "http://" must be marked as insecure: {mirror.url}'
                )
        return v

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.migrate_applications is True and not self.pool:
            raise ValueError('Pool is required when migrating applications.')
        return self


class DockerUpdateResult(BaseModel):
    result: DockerEntry
    """The updated Docker configuration."""


class DockerStatusArgs(BaseModel):
    pass


class StatusResult(BaseModel):
    description: str
    """Human-readable description of the current Docker service status."""
    status: Literal[
        'PENDING', 'RUNNING', 'STOPPED', 'INITIALIZING', 'STOPPING', 'UNCONFIGURED',
        'FAILED', 'MIGRATING', 'MIGRATION_FAILED'
    ]
    """Current state of the Docker service."""


class DockerStatusResult(BaseModel):
    result: StatusResult
    """Current Docker service status information."""


class DockerNvidiaPresentArgs(BaseModel):
    pass


class DockerNvidiaPresentResult(BaseModel):
    result: bool
    """Returns `true` if NVIDIA GPU hardware is present and supported, `false` otherwise."""


class DockerBackupArgs(BaseModel):
    backup_name: NonEmptyString | None = Field(default=None)
    """Name for the backup or `null` to generate a timestamp-based name."""


class DockerBackupResult(BaseModel):
    result: NonEmptyString
    """Name of the created backup."""


class DockerListBackupsArgs(BaseModel):
    pass


class AppInfo(BaseModel):
    id: NonEmptyString
    """Unique identifier of the application."""
    name: NonEmptyString
    """Human-readable name of the application."""
    state: NonEmptyString
    """Current running state of the application."""


class BackupInfo(BaseModel):
    name: NonEmptyString
    """Name of the backup."""
    apps: list[AppInfo]
    """Array of applications included in this backup."""
    snapshot_name: NonEmptyString
    """ZFS snapshot name associated with this backup."""
    created_on: NonEmptyString
    """Timestamp when the backup was created."""
    backup_path: NonEmptyString
    """Filesystem path where the backup is stored."""


class DockerBackupInfo(RootModel[dict[str, BackupInfo]]):
    pass


class DockerListBackupsResult(BaseModel):
    result: DockerBackupInfo
    """Object mapping backup names to their detailed information."""


class DockerRestoreBackupArgs(BaseModel):
    backup_name: NonEmptyString
    """Name of the backup to restore."""


class DockerRestoreBackupResult(BaseModel):
    result: None
    """Returns `null` when the backup restore is successfully started."""


class DockerDeleteBackupArgs(BaseModel):
    backup_name: NonEmptyString
    """Name of the backup to delete."""


class DockerDeleteBackupResult(BaseModel):
    result: None
    """Returns `null` when the backup is successfully deleted."""


class DockerBackupToPoolArgs(BaseModel):
    target_pool: NonEmptyString
    """Name of the storage pool to backup Docker data to."""


class DockerBackupToPoolResult(BaseModel):
    result: None
    """Returns `null` when the pool backup is successfully started."""


class DockerEventsAddedEvent(BaseModel):
    id: str
    """App name."""
    fields: dict
    """Event fields."""


class DockerStateChangedEvent(BaseModel):
    fields: StatusResult
    """Event fields."""
