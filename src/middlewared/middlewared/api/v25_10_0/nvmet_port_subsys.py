from typing import Literal

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

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
    port: dict | None
    subsys: dict | None


class NVMetPortSubsysCreate(NVMetPortSubsysEntry):
    id: Excluded = excluded_field()
    port: Excluded = excluded_field()
    subsys: Excluded = excluded_field()
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
