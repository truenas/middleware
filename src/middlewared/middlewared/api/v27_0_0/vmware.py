from datetime import datetime
from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NotRequired, single_argument_args, single_argument_result,
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


class VMWareEntryState(BaseModel):
    state: Literal["PENDING", "SUCCESS", "ERROR", "BLOCKED"] = Field(
        default=NotRequired,
        description=(
            "VMware host state.\n"
            "\n"
            "* `PENDING`: No snapshot operation on the host was performed yet\n"
            "* `SUCCESS`: The last snapshot operation on the host was successful\n"
            "* `ERROR`: The last snapshot operation on the host failed\n"
            "* `BLOCKED`: Network activity is blocked"
        ),
    )
    error: str = Field(default=NotRequired, description="Error text (if any).")
    datetime_: datetime = Field(alias="datetime", default=NotRequired, description="State update datetime.")


class VMWareEntry(BaseModel):
    id: int = Field(description="Unique identifier for the VMware configuration.")
    datastore: str = Field(description="Valid datastore name which exists on the VMWare host.")
    filesystem: str = Field(description="ZFS filesystem or dataset to use for VMware storage.")
    hostname: str = Field(
        description=(
            "Valid IP address / hostname of a VMWare host. When clustering, this is the vCenter server for the cluster."
        ),
    )
    username: str = Field(description="Credentials used to authorize access to the VMWare host.")
    password: Secret[str] = Field(description="Password for VMware host authentication.")
    state: VMWareEntryState = Field(description="Current connection and synchronization state with the VMware host.")


class VMWareCreate(VMWareEntry):
    id: Excluded = excluded_field()
    state: Excluded = excluded_field()


class VMWareCreateArgs(BaseModel):
    vmware_create: VMWareCreate = Field(description="Configuration for creating a new VMware integration.")


class VMWareCreateResult(BaseModel):
    result: VMWareEntry = Field(description="The newly created VMware integration configuration.")


class VMWareUpdate(VMWareCreate, metaclass=ForUpdateMetaclass):
    pass


class VMWareUpdateArgs(BaseModel):
    id: int = Field(description="ID of the VMware configuration to update.")
    vmware_update: VMWareUpdate = Field(description="Updated configuration for the VMware integration.")


class VMWareUpdateResult(BaseModel):
    result: VMWareEntry = Field(description="The updated VMware integration configuration.")


class VMWareDeleteArgs(BaseModel):
    id: int = Field(description="ID of the VMware configuration to delete.")


class VMWareDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Always returns true on successful VMware configuration deletion.")


@single_argument_args("vmware-creds")
class VMWareGetDatastoresArgs(BaseModel):
    hostname: str = Field(description="IP address or hostname of the VMware host or vCenter server.")
    username: str = Field(description="Username for VMware host authentication.")
    password: Secret[str] = Field(description="Password for VMware host authentication.")


class VMWareGetDatastoresResult(BaseModel):
    result: list[str] = Field(description="Array of available datastore names on the VMware host.")


@single_argument_args("vmware-creds")
class VMWareMatchDatastoresWithDatasetsArgs(BaseModel):
    hostname: str = Field(description="IP address or hostname of the VMware host or vCenter server.")
    username: str = Field(description="Username for VMware host authentication.")
    password: Secret[str] = Field(description="Password for VMware host authentication.")


@single_argument_result
class VMWareMatchDatastoresWithDatasetsResult(BaseModel):
    datastores: list["VMWareMatchDatastoresWithDatasetsResultDatastore"] = Field(
        description="Array of VMware datastores with their matching local filesystems.",
    )
    filesystems: list["VMWareMatchDatastoresWithDatasetsResultFilesystem"] = Field(
        description="Array of local filesystems that can be used for VMware storage.",
    )


class VMWareMatchDatastoresWithDatasetsResultDatastore(BaseModel):
    name: str = Field(description="Name of the VMware datastore.")
    description: str = Field(description="Human-readable description of the datastore.")
    filesystems: list[str] = Field(
        description="Array of local filesystem names that can provide storage for this datastore.",
    )


class VMWareMatchDatastoresWithDatasetsResultFilesystem(BaseModel):
    type: Literal["FILESYSTEM", "VOLUME"] = Field(
        description="Type of storage - FILESYSTEM for ZFS datasets, VOLUME for ZFS volumes.",
    )
    name: str = Field(description="Name of the local filesystem or volume.")
    description: str = Field(description="Human-readable description of the filesystem or volume.")


class VMWareDatasetHasVmsArgs(BaseModel):
    dataset: str = Field(description="ZFS dataset path to check for VMware virtual machines.")
    recursive: bool = Field(description="Whether to check child datasets recursively.")


class VMWareDatasetHasVmsResult(BaseModel):
    result: bool = Field(description="Whether the dataset contains VMware virtual machines.")
