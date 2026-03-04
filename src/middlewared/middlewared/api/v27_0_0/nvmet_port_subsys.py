from typing import Literal

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
    id: int
    """Unique identifier for the port-subsystem association."""
    port: NVMetPortEntry
    """NVMe-oF port that provides access to the subsystem."""
    subsys: NVMetSubsysEntry
    """NVMe-oF subsystem that is accessible through the port."""


class NVMetPortSubsysCreate(BaseModel):
    port_id: int
    """ID of the NVMe-oF port to associate."""
    subsys_id: int
    """ID of the NVMe-oF subsystem to make accessible."""


class NVMetPortSubsysCreateArgs(BaseModel):
    nvmet_port_subsys_create: NVMetPortSubsysCreate
    """Port-subsystem association configuration data for creation."""


class NVMetPortSubsysCreateResult(BaseModel):
    result: NVMetPortSubsysEntry
    """The created port-subsystem association."""


class NVMetPortSubsysUpdate(NVMetPortSubsysCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortSubsysUpdateArgs(BaseModel):
    id: int
    """ID of the port-subsystem association to update."""
    nvmet_port_subsys_update: NVMetPortSubsysUpdate
    """Updated port-subsystem association configuration data."""


class NVMetPortSubsysUpdateResult(BaseModel):
    result: NVMetPortSubsysEntry
    """The updated port-subsystem association."""


class NVMetPortSubsysDeleteArgs(BaseModel):
    id: int
    """ID of the port-subsystem association to delete."""


class NVMetPortSubsysDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the port-subsystem association is successfully deleted."""
