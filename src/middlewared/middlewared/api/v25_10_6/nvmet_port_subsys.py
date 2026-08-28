from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass
from .nvmet_port import NVMetPortEntry
from .nvmet_subsys import NVMetSubsysEntry

__all__ = [
    "NVMetPortSubsysEntry",
    "NVMetPortSubsysCreateArgs",
    "NVMetPortSubsysCreateResult",
    "NVMetPortSubsysUpdateArgs",
    "NVMetPortSubsysUpdateResult",
    "NVMetPortSubsysDeleteArgs",
    "NVMetPortSubsysDeleteResult",
]


class NVMetPortSubsysEntry(BaseModel):
    id: int = Field(description="Unique identifier for the port-subsystem association.")
    port: NVMetPortEntry = Field(description="NVMe-oF port that provides access to the subsystem.")
    subsys: NVMetSubsysEntry = Field(description="NVMe-oF subsystem that is accessible through the port.")


class NVMetPortSubsysCreate(BaseModel):
    port_id: int = Field(description="ID of the NVMe-oF port to associate.")
    subsys_id: int = Field(description="ID of the NVMe-oF subsystem to make accessible.")


class NVMetPortSubsysCreateArgs(BaseModel):
    nvmet_port_subsys_create: NVMetPortSubsysCreate = Field(
        description="Port-subsystem association configuration data for creation.",
    )


class NVMetPortSubsysCreateResult(BaseModel):
    result: NVMetPortSubsysEntry = Field(description="The created port-subsystem association.")


class NVMetPortSubsysUpdate(NVMetPortSubsysCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortSubsysUpdateArgs(BaseModel):
    id: int = Field(description="ID of the port-subsystem association to update.")
    nvmet_port_subsys_update: NVMetPortSubsysUpdate = Field(
        description="Updated port-subsystem association configuration data.",
    )


class NVMetPortSubsysUpdateResult(BaseModel):
    result: NVMetPortSubsysEntry = Field(description="The updated port-subsystem association.")


class NVMetPortSubsysDeleteArgs(BaseModel):
    id: int = Field(description="ID of the port-subsystem association to delete.")


class NVMetPortSubsysDeleteResult(BaseModel):
    result: Literal[True] = Field(
        description="Returns `true` when the port-subsystem association is successfully deleted.",
    )
