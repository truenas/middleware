from typing import Literal, TypeAlias
from typing_extensions import Annotated

from pydantic import StringConstraints

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, Private,
    single_argument_args, single_argument_result,
)


class VirtGlobalEntry(BaseModel):
    id: int
    pool: str | None = None
    dataset: str | None = None
    bridge: str | None = None
    state: Annotated[NonEmptyString, StringConstraints(max_length=200)]


@single_argument_args('virt_global_update')
class VirtGlobalUpdateArgs(BaseModel):
    pool: str | None = None
    bridge: str | None = None


class VirtGlobalUpdateResult(BaseModel):
    result: VirtGlobalEntry


class VirtInstanceEntry(BaseModel):
    id: str
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]


class VirtInstanceCreate(BaseModel):
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    image: Annotated[NonEmptyString, StringConstraints(max_length=200)]


class VirtInstanceCreateArgs(BaseModel):
    container_create: VirtInstanceCreate


class VirtInstanceCreateResult(BaseModel):
    result: int


class VirtInstanceUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    limits_config: str


class VirtInstanceUpdateArgs(BaseModel):
    id: str
    container_update: VirtInstanceUpdate


class VirtInstanceUpdateResult(BaseModel):
    result: VirtInstanceEntry


class VirtInstanceDeleteArgs(BaseModel):
    id: str


class VirtInstanceDeleteResult(BaseModel):
    result: Literal[True]


class VirtInstanceStateArgs(BaseModel):
    id: str
    action: str
    force: bool


class VirtInstanceStateResult(BaseModel):
    result: bool
