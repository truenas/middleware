from typing import Literal

from middlewared.api.base import WWPN, BaseModel, Excluded, FibreChannelHostAlias, ForUpdateMetaclass, excluded_field


class FCHostEntry(BaseModel):
    id: int
    alias: FibreChannelHostAlias
    wwpn: WWPN | None = None
    wwpn_b: WWPN | None = None
    npiv: int = 0


class FCHostCreate(FCHostEntry):
    id: Excluded = excluded_field()


class FCHostCreateArgs(BaseModel):
    fc_host_create: FCHostCreate


class FCHostCreateResult(BaseModel):
    result: FCHostEntry


class FCHostUpdate(FCHostCreate, metaclass=ForUpdateMetaclass):
    pass


class FCHostUpdateArgs(BaseModel):
    id: int
    fc_host_update: FCHostUpdate


class FCHostUpdateResult(BaseModel):
    result: FCHostEntry


class FCHostDeleteArgs(BaseModel):
    id: int


class FCHostDeleteResult(BaseModel):
    result: Literal[True]
