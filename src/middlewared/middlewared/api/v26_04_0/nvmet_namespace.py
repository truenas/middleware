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
    """Unique identifier for the NVMe-oF namespace."""
    nsid: Annotated[int, Field(ge=1, lt=0xFFFFFFFF)] | None = None
    """ Namespace ID (NSID).

    Each namespace within a subsystem has an associated NSID, unique within that subsystem.

    If not supplied during `namespace` creation then the next available NSID will be used.
    """
    subsys: NVMetSubsysEntry
    """NVMe-oF subsystem that contains this namespace."""
    device_type: DeviceType
    """ Type of device (or file) used to implement the namespace. """
    device_path: NonEmptyString
    """
    Path to the device or file being used to implement the namespace.

    When `device_type` is:

    * "ZVOL": `device_path` is e.g. "zvol/poolname/zvolname"
    * "FILE": `device_path` is e.g. "/mnt/poolmnt/path/to/file". The file will be created if necessary.
    """
    dataset: NonEmptyString | None
    """The ZFS dataset name that contains the NVMe-oF namespace device. For file-based namespaces on filesystems \
    (e.g., `/mnt/tank/nvme/namespace1.img`), this is the dataset where the namespace file is stored. For \
    ZVOL-based namespaces with device_path format `zvol/pool/dataset`, this field returns `null` because the \
    device_path is not a filesystem path. This is a read-only field that is automatically populated based on \
    "device_path"."""
    relative_path: str | None
    """The path of the namespace relative to the dataset mountpoint. For file-based namespaces on filesystems, if \
    the device path is `/mnt/tank/nvme/namespace1.img` and the dataset `tank/nvme` is mounted at `/mnt/tank/nvme`, \
    then the relative path is "namespace1.img". An empty string indicates the file is at the dataset root. For \
    ZVOL-based namespaces with device_path format `zvol/pool/dataset`, this field returns `null` because the \
    device_path is not a filesystem path. This is a read-only field that is automatically populated based on \
    "device_path"."""
    filesize: int | None = None
    """When `device_type` is "FILE" then this will be the size of the file in bytes."""
    device_uuid: NonEmptyString
    """Unique device identifier for the namespace."""
    device_nguid: NonEmptyString
    """Namespace Globally Unique Identifier for the namespace."""
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
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    locked: Excluded = excluded_field()
    subsys_id: int
    """ID of the NVMe-oF subsystem to contain this namespace."""
    device_path: NormalPath
    """Normalized path to the device or file for the namespace."""


class NVMetNamespaceCreateArgs(BaseModel):
    nvmet_namespace_create: NVMetNamespaceCreate
    """NVMe-oF namespace configuration data for creation."""


class NVMetNamespaceCreateResult(BaseModel):
    result: NVMetNamespaceEntry
    """The created NVMe-oF namespace configuration."""


class NVMetNamespaceUpdate(NVMetNamespaceCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetNamespaceUpdateArgs(BaseModel):
    id: int
    """ID of the NVMe-oF namespace to update."""
    nvmet_namespace_update: NVMetNamespaceUpdate
    """Updated NVMe-oF namespace configuration data."""


class NVMetNamespaceUpdateResult(BaseModel):
    result: NVMetNamespaceEntry
    """The updated NVMe-oF namespace configuration."""


class NVMetNamespaceDeleteOptions(BaseModel):
    remove: bool = False
    """Remove file underlying namespace if `device_type` is FILE."""


class NVMetNamespaceDeleteArgs(BaseModel):
    id: int
    """ID of the NVMe-oF namespace to delete."""
    options: NVMetNamespaceDeleteOptions = Field(default_factory=NVMetNamespaceDeleteOptions)
    """Options controlling namespace deletion behavior."""


class NVMetNamespaceDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the NVMe-oF namespace is successfully deleted."""
