from typing import Annotated, Literal, TypeAlias

from pydantic import Field, model_validator

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
    filesize: int | None = None
    device_uuid: NonEmptyString
    device_nguid: NonEmptyString
    enabled: bool = True
    locked: bool | None

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.device_type == 'FILE':
            if self.filesize is None:
                raise ValueError('filesize must be supplied when device_type is FILE')

        return self


class NVMetNamespaceCreate(NVMetNamespaceEntry):
    id: Excluded = excluded_field()
    subsys: Excluded = excluded_field()
    device_uuid: Excluded = excluded_field()
    device_nguid: Excluded = excluded_field()
    locked: Excluded = excluded_field()
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


class NVMetNamespaceDeleteOptions(BaseModel):
    remove: bool = False
    """Remove file underlying namespace if `device_type` is FILE."""


class NVMetNamespaceDeleteArgs(BaseModel):
    id: int
    options: NVMetNamespaceDeleteOptions = Field(default_factory=NVMetNamespaceDeleteOptions)


class NVMetNamespaceDeleteResult(BaseModel):
    result: Literal[True]
