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
    id: int = Field(description="Unique identifier for the NVMe-oF namespace.")
    nsid: Annotated[int, Field(ge=1, lt=0xFFFFFFFF)] | None = Field(
        default=None,
        description=(
            "Namespace ID (NSID).\n"
            "\n"
            "Each namespace within a subsystem has an associated NSID, unique within that subsystem.\n"
            "\n"
            "If not supplied during `namespace` creation then the next available NSID will be used."
        ),
    )
    subsys: NVMetSubsysEntry = Field(description="NVMe-oF subsystem that contains this namespace.")
    device_type: DeviceType = Field(description="Type of device (or file) used to implement the namespace.")
    device_path: NonEmptyString = Field(
        description=(
            "Path to the device or file being used to implement the namespace.\n"
            "\n"
            "When `device_type` is:\n"
            "\n"
            "* \"ZVOL\": `device_path` is e.g. \"zvol/poolname/zvolname\"\n"
            "* \"FILE\": `device_path` is e.g. \"/mnt/poolmnt/path/to/file\". The file will be created if necessary."
        ),
    )
    dataset: str | None = Field(
        description=(
            "The ZFS dataset containing the file-based namespace (e.g., 'tank/nvmet'). Returns `null` for ZVOL-based "
            "namespaces or if the FILE path cannot be resolved yet (encrypted dataset not unlocked, etc.). This is a "
            "read-only field automatically populated from \"device_path\"."
        ),
    )
    relative_path: str | None = Field(
        description=(
            "The path of the file-based namespace relative to the dataset mountpoint (e.g., 'namespaces/ns1.img'). An "
            "empty string indicates the file is at the dataset root. Returns `null` for ZVOL-based namespaces or if the"
            " path cannot be resolved yet. This is a read-only field automatically populated from \"device_path\"."
        ),
    )
    filesize: int | None = Field(
        default=None,
        description="When `device_type` is \"FILE\" then this will be the size of the file in bytes.",
    )
    device_uuid: NonEmptyString = Field(description="Unique device identifier for the namespace.")
    device_nguid: NonEmptyString = Field(description="Namespace Globally Unique Identifier for the namespace.")
    enabled: bool = Field(
        default=True,
        description=(
            "If `enabled` is `False` then the namespace will not be accessible.\n"
            "\n"
            "Some namespace configuration changes are blocked when that namespace is enabled."
        ),
    )
    locked: bool | None = Field(
        description=(
            "Reflect the locked state of the namespace.\n"
            "\n"
            "The underlying `device_path` could be an encrypted ZVOL, or a file on an encrypted dataset. In either case"
            " `locked` will be `True` if the underlying entity is locked."
        ),
    )


class NVMetNamespaceCreate(NVMetNamespaceEntry):
    id: Excluded = excluded_field()
    subsys: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    device_uuid: Excluded = excluded_field()
    device_nguid: Excluded = excluded_field()
    locked: Excluded = excluded_field()
    subsys_id: int = Field(description="ID of the NVMe-oF subsystem to contain this namespace.")
    device_path: NormalPath = Field(description="Normalized path to the device or file for the namespace.")


class NVMetNamespaceCreateArgs(BaseModel):
    nvmet_namespace_create: NVMetNamespaceCreate = Field(
        description="NVMe-oF namespace configuration data for creation.",
    )


class NVMetNamespaceCreateResult(BaseModel):
    result: NVMetNamespaceEntry = Field(description="The created NVMe-oF namespace configuration.")


class NVMetNamespaceUpdate(NVMetNamespaceCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetNamespaceUpdateArgs(BaseModel):
    id: int = Field(description="ID of the NVMe-oF namespace to update.")
    nvmet_namespace_update: NVMetNamespaceUpdate = Field(description="Updated NVMe-oF namespace configuration data.")


class NVMetNamespaceUpdateResult(BaseModel):
    result: NVMetNamespaceEntry = Field(description="The updated NVMe-oF namespace configuration.")


class NVMetNamespaceDeleteOptions(BaseModel):
    remove: bool = Field(default=False, description="Remove file underlying namespace if `device_type` is FILE.")


class NVMetNamespaceDeleteArgs(BaseModel):
    id: int = Field(description="ID of the NVMe-oF namespace to delete.")
    options: NVMetNamespaceDeleteOptions = Field(
        default_factory=NVMetNamespaceDeleteOptions,
        description="Options controlling namespace deletion behavior.",
    )


class NVMetNamespaceDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the NVMe-oF namespace is successfully deleted.")
