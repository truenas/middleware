from typing import Literal

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
    id: int
    """Unique identifier for the host-subsystem association."""
    host: NVMetHostEntry
    """NVMe-oF host that is authorized to access the subsystem."""
    subsys: NVMetSubsysEntry
    """NVMe-oF subsystem that the host is authorized to access."""


class NVMetHostSubsysCreate(BaseModel):
    host_id: int
    """ID of the NVMe-oF host to authorize."""
    subsys_id: int
    """ID of the NVMe-oF subsystem to grant access to."""


class NVMetHostSubsysCreateArgs(BaseModel):
    nvmet_host_subsys_create: NVMetHostSubsysCreate
    """Host-subsystem association configuration data for creation."""


class NVMetHostSubsysCreateResult(BaseModel):
    result: NVMetHostSubsysEntry
    """The created host-subsystem association."""


class NVMetHostSubsysUpdate(NVMetHostSubsysCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetHostSubsysUpdateArgs(BaseModel):
    id: int
    """ID of the host-subsystem association to update."""
    nvmet_host_subsys_update: NVMetHostSubsysUpdate
    """Updated host-subsystem association configuration data."""


class NVMetHostSubsysUpdateResult(BaseModel):
    result: NVMetHostSubsysEntry
    """The updated host-subsystem association."""


class NVMetHostSubsysDeleteArgs(BaseModel):
    id: int
    """ID of the host-subsystem association to delete."""


class NVMetHostSubsysDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the host-subsystem association is successfully deleted."""
