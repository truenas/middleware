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
    port: NVMetPortEntry
    subsys: NVMetSubsysEntry


class NVMetPortSubsysCreate(BaseModel):
    port_id: int
    subsys_id: int


class NVMetPortSubsysCreateArgs(BaseModel):
    nvmet_port_subsys_create: NVMetPortSubsysCreate


class NVMetPortSubsysCreateResult(BaseModel):
    result: NVMetPortSubsysEntry


class NVMetPortSubsysUpdate(NVMetPortSubsysCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetPortSubsysUpdateArgs(BaseModel):
    id: int
    nvmet_port_subsys_update: NVMetPortSubsysUpdate


class NVMetPortSubsysUpdateResult(BaseModel):
    result: NVMetPortSubsysEntry


class NVMetPortSubsysDeleteArgs(BaseModel):
    id: int


class NVMetPortSubsysDeleteResult(BaseModel):
    result: Literal[True]
