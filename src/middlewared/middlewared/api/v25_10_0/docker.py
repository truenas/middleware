from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import IPvAnyInterface, Field, field_validator, model_validator, RootModel

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, HttpUrl, NonEmptyString, single_argument_args,
)


__all__ = [
    'DockerEntry', 'DockerUpdateArgs', 'DockerUpdateResult', 'DockerStatusArgs', 'DockerStatusResult',
    'DockerNvidiaPresentArgs', 'DockerNvidiaPresentResult', 'DockerBackupArgs', 'DockerBackupResult',
    'DockerListBackupsArgs', 'DockerListBackupsResult', 'DockerRestoreBackupArgs', 'DockerRestoreBackupResult',
    'DockerDeleteBackupArgs', 'DockerDeleteBackupResult', 'DockerBackupToPoolArgs', 'DockerBackupToPoolResult',
]


class AddressPool(BaseModel):
    base: IPvAnyInterface = Field(description="Base network address with prefix for the pool.")
    size: Annotated[int, Field(ge=1)] = Field(description="Subnet size for networks allocated from this pool.")

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


class DockerEntry(BaseModel):
    id: int = Field(description="Unique identifier for the Docker configuration.")
    enable_image_updates: bool = Field(description="Whether automatic Docker image updates are enabled.")
    dataset: NonEmptyString | None = Field(description="ZFS dataset used for Docker data storage or `null`.")
    pool: NonEmptyString | None = Field(description="Storage pool used for Docker or `null` if not configured.")
    nvidia: bool = Field(description="Whether NVIDIA GPU support is enabled for containers.")
    address_pools: list[dict] = Field(description="Array of network address pools for container networking.")
    cidr_v6: str = Field(description="IPv6 CIDR block for Docker container networking.")
    secure_registry_mirrors: list[HttpUrl] = Field(description="Array of secure (HTTPS) registry mirror URLs.")
    insecure_registry_mirrors: list[HttpUrl] = Field(description="Array of insecure (HTTP) registry mirror URLs.")


@single_argument_args('docker_update')
class DockerUpdateArgs(DockerEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    address_pools: list[AddressPool] = Field(description="Array of network address pools for container networking.")
    cidr_v6: IPvAnyInterface = Field(description="IPv6 CIDR block for Docker container networking.")
    migrate_applications: bool = Field(description="Whether to migrate existing applications when changing pools.")
    secure_registry_mirrors: list[HttpUrl] = Field(description="Array of secure (HTTPS) registry mirror URLs.")
    insecure_registry_mirrors: list[HttpUrl] = Field(description="Array of insecure (HTTP) registry mirror URLs.")

    @field_validator('cidr_v6')
    @classmethod
    def validate_ipv6(cls, v):
        if v.version != 6:
            raise ValueError('cidr_v6 must be an IPv6 address.')
        if v.network.prefixlen == 128:
            raise ValueError('Prefix length of cidr_v6 network cannot be 128.')
        return v

    @field_validator('secure_registry_mirrors')
    @classmethod
    def validate_secure_registries(cls, v):
        for url in v:
            parsed = urlparse(url)
            if parsed.scheme == 'http':
                raise ValueError(f'Secure registry mirror {url} cannot use HTTP protocol.')
        return v

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.migrate_applications is True and not self.pool:
            raise ValueError('Pool is required when migrating applications.')
        return self


class DockerUpdateResult(BaseModel):
    result: DockerEntry = Field(description="The updated Docker configuration.")


class DockerStatusArgs(BaseModel):
    pass


class StatusResult(BaseModel):
    description: str = Field(description="Human-readable description of the current Docker service status.")
    status: Literal['PENDING', 'RUNNING', 'STOPPED', 'INITIALIZING', 'STOPPING', 'UNCONFIGURED', 'FAILED'] = Field(
        description="Current state of the Docker service.",
    )


class DockerStatusResult(BaseModel):
    result: StatusResult = Field(description="Current Docker service status information.")


class DockerNvidiaPresentArgs(BaseModel):
    pass


class DockerNvidiaPresentResult(BaseModel):
    result: bool = Field(
        description="Returns `true` if NVIDIA GPU hardware is present and supported, `false` otherwise.",
    )


class DockerBackupArgs(BaseModel):
    backup_name: NonEmptyString | None = Field(
        default=None,
        description="Name for the backup or `null` to generate a timestamp-based name.",
    )


class DockerBackupResult(BaseModel):
    result: NonEmptyString = Field(description="Name of the created backup.")


class DockerListBackupsArgs(BaseModel):
    pass


class AppInfo(BaseModel):
    id: NonEmptyString = Field(description="Unique identifier of the application.")
    name: NonEmptyString = Field(description="Human-readable name of the application.")
    state: NonEmptyString = Field(description="Current running state of the application.")


class BackupInfo(BaseModel):
    name: NonEmptyString = Field(description="Name of the backup.")
    apps: list[AppInfo] = Field(description="Array of applications included in this backup.")
    snapshot_name: NonEmptyString = Field(description="ZFS snapshot name associated with this backup.")
    created_on: NonEmptyString = Field(description="Timestamp when the backup was created.")
    backup_path: NonEmptyString = Field(description="Filesystem path where the backup is stored.")


class DockerBackupInfo(RootModel[dict[str, BackupInfo]]):
    pass


class DockerListBackupsResult(BaseModel):
    result: DockerBackupInfo = Field(description="Object mapping backup names to their detailed information.")


class DockerRestoreBackupArgs(BaseModel):
    backup_name: NonEmptyString = Field(description="Name of the backup to restore.")


class DockerRestoreBackupResult(BaseModel):
    result: None = Field(description="Returns `null` when the backup restore is successfully started.")


class DockerDeleteBackupArgs(BaseModel):
    backup_name: NonEmptyString = Field(description="Name of the backup to delete.")


class DockerDeleteBackupResult(BaseModel):
    result: None = Field(description="Returns `null` when the backup is successfully deleted.")


class DockerBackupToPoolArgs(BaseModel):
    target_pool: NonEmptyString = Field(description="Name of the storage pool to backup Docker data to.")


class DockerBackupToPoolResult(BaseModel):
    result: None = Field(description="Returns `null` when the pool backup is successfully started.")
