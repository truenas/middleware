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
    datastore: str
    """Valid datastore name which exists on the VMWare host."""
    filesystem: str
    hostname: str
    """Valid IP address / hostname of a VMWare host. When clustering, this is the vCenter server for the cluster."""
    username: str
    """Credentials used to authorize access to the VMWare host."""
    password: Secret[str]
    state: dict


class VMWareCreate(VMWareEntry):
    id: Excluded = excluded_field()
    state: Excluded = excluded_field()


class VMWareCreateArgs(BaseModel):
    vmware_create: VMWareCreate


class VMWareCreateResult(BaseModel):
    result: VMWareEntry


class VMWareUpdate(VMWareCreate, metaclass=ForUpdateMetaclass):
    pass


class VMWareUpdateArgs(BaseModel):
    id: int
    vmware_update: VMWareUpdate


class VMWareUpdateResult(BaseModel):
    result: VMWareEntry


class VMWareDeleteArgs(BaseModel):
    id: int


class VMWareDeleteResult(BaseModel):
    result: Literal[True]


@single_argument_args("vmware-creds")
class VMWareGetDatastoresArgs(BaseModel):
    hostname: str
    username: str
    password: Secret[str]


class VMWareGetDatastoresResult(BaseModel):
    result: list[str]


@single_argument_args("vmware-creds")
class VMWareMatchDatastoresWithDatasetsArgs(BaseModel):
    hostname: str
    username: str
    password: Secret[str]


@single_argument_result
class VMWareMatchDatastoresWithDatasetsResult(BaseModel):
    datastores: list["VMWareMatchDatastoresWithDatasetsResultDatastore"]
    filesystems: list["VMWareMatchDatastoresWithDatasetsResultFilesystem"]


class VMWareMatchDatastoresWithDatasetsResultDatastore(BaseModel):
    name: str
    description: str
    filesystems: list[str]


class VMWareMatchDatastoresWithDatasetsResultFilesystem(BaseModel):
    type: Literal["FILESYSTEM", "VOLUME"]
    name: str
    description: str


class VMWareDatasetHasVmsArgs(BaseModel):
    dataset: str
    recursive: bool


class VMWareDatasetHasVmsResult(BaseModel):
    result: bool
