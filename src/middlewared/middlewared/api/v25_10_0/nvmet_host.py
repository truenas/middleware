from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "NVMetHostEntry",
    "NVMetHostCreateArgs",
    "NVMetHostCreateResult",
    "NVMetHostUpdateArgs",
    "NVMetHostUpdateResult",
    "NVMetHostDeleteArgs",
    "NVMetHostDeleteResult",
]


class NVMetHostEntry(BaseModel):
    id: int
    hostnqn: NonEmptyString
    dhchap_key: Secret[NonEmptyString | None] = None
    dhchap_ctrl_key: Secret[NonEmptyString | None] = None
    dhchap_dhgroup: Literal['2048-BIT', '3072-BIT', '4096-BIT', '6144-BIT', '8192-BIT'] | None = None
    dhchap_hash: Literal['SHA-256', 'SHA-384', 'SHA-512'] = 'SHA-256'


class NVMetHostCreate(NVMetHostEntry):
    id: Excluded = excluded_field()


class NVMetHostCreateArgs(BaseModel):
    nvmet_host_create: NVMetHostCreate


class NVMetHostCreateResult(BaseModel):
    result: NVMetHostEntry


class NVMetHostUpdate(NVMetHostCreate, metaclass=ForUpdateMetaclass):
    pass


class NVMetHostUpdateArgs(BaseModel):
    id: int
    nvmet_host_update: NVMetHostUpdate


class NVMetHostUpdateResult(BaseModel):
    result: NVMetHostEntry


class NVMetHostDeleteOptions(BaseModel):
    force: bool = False


class NVMetHostDeleteArgs(BaseModel):
    id: int
    options: NVMetHostDeleteOptions = Field(default_factory=NVMetHostDeleteOptions)


class NVMetHostDeleteResult(BaseModel):
    result: Literal[True]
