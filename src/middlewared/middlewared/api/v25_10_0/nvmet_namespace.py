from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "NVMetNamespaceEntry",
    "NVMetNamespaceCreateArgs",
    "NVMetNamespaceCreateResult",
    "NVMetNamespaceUpdateArgs",
    "NVMetNamespaceUpdateResult",
    "NVMetNamespaceDeleteArgs",
    "NVMetNamespaceDeleteResult",
]


DeviceType: TypeAlias = Literal['ZVOL', 'FILE']


class NVMetNamespaceEntry(BaseModel):
    id: int
    nsid: Annotated[int, Field(ge=1, lt=0xFFFFFFFF)] | None = None
    subsys: dict | None
    device_type: DeviceType
    device_path: str
    device_uuid: NonEmptyString
    device_nguid: NonEmptyString
    enabled: bool = True


class NVMetNamespaceCreate(NVMetNamespaceEntry):
    id: Excluded = excluded_field()
    subsys: Excluded = excluded_field()
    device_uuid: Excluded = excluded_field()
    device_nguid: Excluded = excluded_field()
    subsys_id: int


class NVMetNamespaceCreateArgs(BaseModel):
    nvmet_namespace_create: NVMetNamespaceCreate


class NVMetNamespaceCreateResult(BaseModel):
    result: NVMetNamespaceEntry


class NVMetNamespaceUpdate(NVMetNamespaceCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetNamespaceUpdateArgs(BaseModel):
    id: int
    nvmet_namespace_update: NVMetNamespaceUpdate


class NVMetNamespaceUpdateResult(BaseModel):
    result: NVMetNamespaceEntry


class NVMetNamespaceDeleteArgs(BaseModel):
    id: int


class NVMetNamespaceDeleteResult(BaseModel):
    result: Literal[True]
