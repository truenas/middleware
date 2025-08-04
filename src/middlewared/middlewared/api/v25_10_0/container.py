import uuid

from typing import Literal

from pydantic import Field, field_validator

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)


__all__ = [
    'ContainerEntry',
    'ContainerCreateArgs', 'ContainerCreateResult',
    'ContainerUpdateArgs', 'ContainerUpdateResult',
    'ContainerDeleteArgs', 'ContainerDeleteResult',
    'ContainerStartArgs', 'ContainerStartResult',
    'ContainerStopArgs', 'ContainerStopResult',
]


class ContainerStatus(BaseModel):
    state: NonEmptyString
    pid: int | None
    domain_state: NonEmptyString | None


class ContainerEntry(BaseModel):
    id: int
    uuid: str | None = None
    name: NonEmptyString
    description: str = ''
    vcpus: int = Field(ge=1, default=1)
    cores: int = Field(ge=1, default=1)
    threads: int = Field(ge=1, default=1)
    cpuset: str | None = None  # TODO: Add validation for numeric set
    memory: int = Field(ge=20)
    autostart: bool = True
    time: Literal['LOCAL', 'UTC'] = 'LOCAL'
    shutdown_timeout: int = Field(ge=5, le=300, default=90)
    dataset: str
    init: str
    status: ContainerStatus


class ContainerCreate(ContainerEntry):
    id: Excluded = excluded_field()
    status: Excluded = excluded_field()

    @field_validator('uuid')
    def validate_uuid(cls, value):
        if value is not None:
            try:
                uuid.UUID(value, version=4)
            except ValueError:
                raise ValueError('UUID is not valid version 4')

        return value


@single_argument_args('container_create')
class ContainerCreateArgs(ContainerCreate):
    pass


class ContainerCreateResult(BaseModel):
    result: ContainerEntry


class ContainerUpdate(ContainerCreate, metaclass=ForUpdateMetaclass):
    pass


class ContainerUpdateArgs(BaseModel):
    id: int
    container_update: ContainerUpdate


class ContainerUpdateResult(BaseModel):
    result: ContainerEntry


class ContainerDeleteArgs(BaseModel):
    id: int


class ContainerDeleteResult(BaseModel):
    result: None


class ContainerStartArgs(BaseModel):
    id: int


class ContainerStartResult(BaseModel):
    result: None


class ContainerStopOptions(BaseModel):
    force: bool = False
    force_after_timeout: bool = False


class ContainerStopArgs(BaseModel):
    id: int
    options: ContainerStopOptions = ContainerStopOptions()


class ContainerStopResult(BaseModel):
    result: None
