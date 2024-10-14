from typing import Literal

from middlewared.api.base import BaseModel, Excluded, FibreChannelPortAlias, ForUpdateMetaclass, WWPN, excluded_field


class FCPortEntry(BaseModel):
    id: int
    port: FibreChannelPortAlias
    wwpn: WWPN | None
    wwpn_b: WWPN | None
    target_id: int


class FCPortCreate(FCPortEntry):
    id: Excluded = excluded_field()
    wwpn: Excluded = excluded_field()
    wwpn_b: Excluded = excluded_field()


class FCPortCreateArgs(BaseModel):
    fc_Port_create: FCPortCreate


class FCPortCreateResult(BaseModel):
    result: FCPortEntry


class FCPortUpdate(FCPortCreate, metaclass=ForUpdateMetaclass):
    pass


class FCPortUpdateArgs(BaseModel):
    id: int
    fc_Port_update: FCPortUpdate


class FCPortUpdateResult(BaseModel):
    result: FCPortEntry


class FCPortDeleteArgs(BaseModel):
    id: int


class FCPortDeleteResult(BaseModel):
    result: Literal[True]
