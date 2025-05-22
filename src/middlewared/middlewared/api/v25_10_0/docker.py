from typing import Annotated, Literal

from pydantic import IPvAnyInterface, Field, field_validator, model_validator, RootModel

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)


__all__ = [
    'DockerEntry', 'DockerUpdateArgs', 'DockerUpdateResult', 'DockerStatusArgs', 'DockerStatusResult',
    'DockerNvidiaPresentArgs', 'DockerNvidiaPresentResult', 'DockerBackupArgs', 'DockerBackupResult',
    'DockerListBackupArgs', 'DockerListBackupResult', 'DockerRestoreBackupArgs', 'DockerRestoreBackupResult',
    'DockerDeleteBackupArgs', 'DockerDeleteBackupResult', 'DockerBackupToPoolArgs', 'DockerBackupToPoolResult',
]


class AddressPool(BaseModel):
    base: IPvAnyInterface
    size: Annotated[int, Field(ge=1)]

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
    id: int
    enable_image_updates: bool
    dataset: NonEmptyString | None
    pool: NonEmptyString | None
    nvidia: bool
    address_pools: list[dict]
    cidr_v6: str


@single_argument_args('docker_update')
class DockerUpdateArgs(DockerEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    address_pools: list[AddressPool]
    cidr_v6: IPvAnyInterface
    migrate_applications: bool

    @field_validator('cidr_v6')
    @classmethod
    def validate_ipv6(cls, v):
        if v.version != 6:
            raise ValueError('cidr_v6 must be an IPv6 address.')
        if v.network.prefixlen == 128:
            raise ValueError('Prefix length of cidr_v6 network cannot be 128.')
        return v

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.migrate_applications is True and not self.pool:
            raise ValueError('Pool is required when migrating applications.')
        return self


class DockerUpdateResult(BaseModel):
    result: DockerEntry


class DockerStatusArgs(BaseModel):
    pass


class StatusResult(BaseModel):
    description: str
    status: Literal['PENDING', 'RUNNING', 'STOPPED', 'INITIALIZING', 'STOPPING', 'UNCONFIGURED', 'FAILED']


class DockerStatusResult(BaseModel):
    result: StatusResult


class DockerNvidiaPresentArgs(BaseModel):
    pass


class DockerNvidiaPresentResult(BaseModel):
    result: bool


class DockerBackupArgs(BaseModel):
    backup_name: NonEmptyString | None = Field(default=None)


class DockerBackupResult(BaseModel):
    result: NonEmptyString


class DockerListBackupArgs(BaseModel):
    pass


class AppInfo(BaseModel):
    id: NonEmptyString
    name: NonEmptyString
    state: NonEmptyString


class BackupInfo(BaseModel):
    name: NonEmptyString
    apps: list[AppInfo]
    snapshot_name: NonEmptyString
    created_on: NonEmptyString
    backup_path: NonEmptyString


class DockerBackupInfo(RootModel[dict[str, BackupInfo]]):
    pass


class DockerListBackupResult(BaseModel):
    result: DockerBackupInfo


class DockerRestoreBackupArgs(BaseModel):
    backup_name: NonEmptyString


class DockerRestoreBackupResult(BaseModel):
    result: None


class DockerDeleteBackupArgs(BaseModel):
    backup_name: NonEmptyString


class DockerDeleteBackupResult(BaseModel):
    result: None


class DockerBackupToPoolArgs(BaseModel):
    target_pool: NonEmptyString


class DockerBackupToPoolResult(BaseModel):
    result: None
