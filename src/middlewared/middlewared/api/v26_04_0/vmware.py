from typing import Literal

from pydantic import Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args, single_argument_result,
)

__all__ = [
    "VMWareEntry",
    "VMWareCreateArgs", "VMWareCreateResult",
    "VMWareUpdateArgs", "VMWareUpdateResult",
    "VMWareDeleteArgs", "VMWareDeleteResult",
    "VMWareGetDatastoresArgs", "VMWareGetDatastoresResult",
    "VMWareMatchDatastoresWithDatasetsArgs", "VMWareMatchDatastoresWithDatasetsResult",
    "VMWareDatasetHasVmsArgs", "VMWareDatasetHasVmsResult",
]


class VMWareEntry(BaseModel):
    id: int
    """Unique identifier for the VMware configuration."""
    datastore: str
    """Valid datastore name which exists on the VMWare host."""
    filesystem: str
    """ZFS filesystem or dataset to use for VMware storage."""
    hostname: str
    """Valid IP address / hostname of a VMWare host. When clustering, this is the vCenter server for the cluster."""
    username: str
    """Credentials used to authorize access to the VMWare host."""
    password: Secret[str]
    """Password for VMware host authentication."""
    state: dict
    """Current connection and synchronization state with the VMware host."""


class VMWareCreate(VMWareEntry):
    id: Excluded = excluded_field()
    state: Excluded = excluded_field()


class VMWareCreateArgs(BaseModel):
    vmware_create: VMWareCreate
    """Configuration for creating a new VMware integration."""


class VMWareCreateResult(BaseModel):
    result: VMWareEntry
    """The newly created VMware integration configuration."""


class VMWareUpdate(VMWareCreate, metaclass=ForUpdateMetaclass):
    pass


class VMWareUpdateArgs(BaseModel):
    id: int
    """ID of the VMware configuration to update."""
    vmware_update: VMWareUpdate
    """Updated configuration for the VMware integration."""


class VMWareUpdateResult(BaseModel):
    result: VMWareEntry
    """The updated VMware integration configuration."""


class VMWareDeleteArgs(BaseModel):
    id: int
    """ID of the VMware configuration to delete."""


class VMWareDeleteResult(BaseModel):
    result: Literal[True]
    """Always returns true on successful VMware configuration deletion."""


@single_argument_args("vmware-creds")
class VMWareGetDatastoresArgs(BaseModel):
    hostname: str
    """IP address or hostname of the VMware host or vCenter server."""
    username: str
    """Username for VMware host authentication."""
    password: Secret[str]
    """Password for VMware host authentication."""


class VMWareGetDatastoresResult(BaseModel):
    result: list[str]
    """Array of available datastore names on the VMware host."""


@single_argument_args("vmware-creds")
class VMWareMatchDatastoresWithDatasetsArgs(BaseModel):
    hostname: str
    """IP address or hostname of the VMware host or vCenter server."""
    username: str
    """Username for VMware host authentication."""
    password: Secret[str]
    """Password for VMware host authentication."""


@single_argument_result
class VMWareMatchDatastoresWithDatasetsResult(BaseModel):
    datastores: list["VMWareMatchDatastoresWithDatasetsResultDatastore"]
    """Array of VMware datastores with their matching local filesystems."""
    filesystems: list["VMWareMatchDatastoresWithDatasetsResultFilesystem"]
    """Array of local filesystems that can be used for VMware storage."""


class VMWareMatchDatastoresWithDatasetsResultDatastore(BaseModel):
    name: str
    """Name of the VMware datastore."""
    description: str
    """Human-readable description of the datastore."""
    filesystems: list[str]
    """Array of local filesystem names that can provide storage for this datastore."""


class VMWareMatchDatastoresWithDatasetsResultFilesystem(BaseModel):
    type: Literal["FILESYSTEM", "VOLUME"]
    """Type of storage - FILESYSTEM for ZFS datasets, VOLUME for ZFS volumes."""
    name: str
    """Name of the local filesystem or volume."""
    description: str
    """Human-readable description of the filesystem or volume."""


class VMWareDatasetHasVmsArgs(BaseModel):
    dataset: str
    """ZFS dataset path to check for VMware virtual machines."""
    recursive: bool
    """Whether to check child datasets recursively."""


class VMWareDatasetHasVmsResult(BaseModel):
    result: bool
    """Whether the dataset contains VMware virtual machines."""
