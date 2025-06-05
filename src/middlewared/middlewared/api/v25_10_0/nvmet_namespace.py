from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NormalPath, NonEmptyString, excluded_field
from .nvmet_subsys import NVMetSubsysEntry

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
    """ Namespace ID (NSID)

    Each namespace within a subsystem has an associated NSID, unique within that subsystem.

    If not supplied during `namespace` creation then the next available NSID will be used.
    """
    subsys: NVMetSubsysEntry
    device_type: DeviceType
    """ Type of device (or file) used to implement the namespace. """
    device_path: NonEmptyString
    """
    Path to the device or file being used to implement the namespace.

    When `device_type` is:

    * "ZVOL": `device_path` is e.g. "zvol/poolname/zvolname"
    * "FILE": `device_path` is e.g. "/mnt/poolmnt/path/to/file". The file will be created if necessary.
    """
    filesize: int | None = None
    """When `device_type` is "FILE" then this will be the size of the file in bytes."""
    device_uuid: NonEmptyString
    device_nguid: NonEmptyString
    enabled: bool = True
    """
    If `enabled` is `False` then the namespace will not be accessible.

    Some namespace configuration changes are blocked when that namespace is enabled.
    """
    locked: bool | None
    """
    Reflect the locked state of the namespace.

    The underlying `device_path` could be an encrypted ZVOL, or a file on an encrypted dataset. In either case \
    `locked` will be `True` if the underlying entity is locked.
    """


class NVMetNamespaceCreate(NVMetNamespaceEntry):
    id: Excluded = excluded_field()
    subsys: Excluded = excluded_field()
    device_uuid: Excluded = excluded_field()
    device_nguid: Excluded = excluded_field()
    locked: Excluded = excluded_field()
    subsys_id: int
    device_path: NormalPath


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
