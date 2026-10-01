from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass

from .nvmet_host import NVMetHostEntry
from .nvmet_subsys import NVMetSubsysEntry

__all__ = [
    "NVMetHostSubsysEntry",
    "NVMetHostSubsysCreateArgs",
    "NVMetHostSubsysCreateResult",
    "NVMetHostSubsysUpdateArgs",
    "NVMetHostSubsysUpdateResult",
    "NVMetHostSubsysDeleteArgs",
    "NVMetHostSubsysDeleteResult",
]


class NVMetHostSubsysEntry(BaseModel):
    id: int = Field(description="Unique identifier for the host-subsystem association.")
    host: NVMetHostEntry = Field(description="NVMe-oF host that is authorized to access the subsystem.")
    subsys: NVMetSubsysEntry = Field(description="NVMe-oF subsystem that the host is authorized to access.")


class NVMetHostSubsysCreate(BaseModel):
    host_id: int = Field(description="ID of the NVMe-oF host to authorize.")
    subsys_id: int = Field(description="ID of the NVMe-oF subsystem to grant access to.")


class NVMetHostSubsysCreateArgs(BaseModel):
    nvmet_host_subsys_create: NVMetHostSubsysCreate = Field(
        description="Host-subsystem association configuration data for creation.",
    )


class NVMetHostSubsysCreateResult(BaseModel):
    result: NVMetHostSubsysEntry = Field(description="The created host-subsystem association.")


class NVMetHostSubsysUpdate(NVMetHostSubsysCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetHostSubsysUpdateArgs(BaseModel):
    id: int = Field(description="ID of the host-subsystem association to update.")
    nvmet_host_subsys_update: NVMetHostSubsysUpdate = Field(
        description="Updated host-subsystem association configuration data.",
    )


class NVMetHostSubsysUpdateResult(BaseModel):
    result: NVMetHostSubsysEntry = Field(description="The updated host-subsystem association.")


class NVMetHostSubsysDeleteArgs(BaseModel):
    id: int = Field(description="ID of the host-subsystem association to delete.")


class NVMetHostSubsysDeleteResult(BaseModel):
    result: Literal[True] = Field(
        description="Returns `true` when the host-subsystem association is successfully deleted.",
    )
