from typing import Literal

from middlewared.api.base import BaseModel, ForUpdateMetaclass

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
    host: dict | None
    subsys: dict | None


class NVMetHostSubsysCreate(BaseModel):
    host_id: int
    subsys_id: int


class NVMetHostSubsysCreateArgs(BaseModel):
    nvmet_host_subsys_create: NVMetHostSubsysCreate


class NVMetHostSubsysCreateResult(BaseModel):
    result: NVMetHostSubsysEntry


class NVMetHostSubsysUpdate(NVMetHostSubsysCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetHostSubsysUpdateArgs(BaseModel):
    id: int
    nvmet_host_subsys_update: NVMetHostSubsysUpdate


class NVMetHostSubsysUpdateResult(BaseModel):
    result: NVMetHostSubsysEntry


class NVMetHostSubsysDeleteArgs(BaseModel):
    id: int


class NVMetHostSubsysDeleteResult(BaseModel):
    result: Literal[True]
