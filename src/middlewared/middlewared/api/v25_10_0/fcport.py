from typing import Literal

from pydantic import Field

from middlewared.api.base import WWPN, BaseModel, Excluded, FibreChannelPortAlias, ForUpdateMetaclass, excluded_field
from .common import QueryArgs


__all__ = [
    "FCPortEntry", "FCPortCreateArgs", "FCPortCreateResult", "FCPortUpdateArgs", "FCPortUpdateResult",
    "FCPortDeleteArgs", "FCPortDeleteResult", "FCPortPortChoicesArgs", "FCPortPortChoicesResult", "FCPortStatusArgs",
    "FCPortStatusResult",
]


class FCPortEntry(BaseModel):
    id: int
    port: FibreChannelPortAlias
    wwpn: WWPN | None
    wwpn_b: WWPN | None
    target: dict | None


class FCPortCreate(FCPortEntry):
    id: Excluded = excluded_field()
    wwpn: Excluded = excluded_field()
    wwpn_b: Excluded = excluded_field()
    target: Excluded = excluded_field()
    target_id: int


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


class FCPortChoiceEntry(BaseModel):
    wwpn: WWPN | None
    wwpn_b: WWPN | None


class FCPortPortChoicesArgs(BaseModel):
    include_used: bool = True


class FCPortPortChoicesResult(BaseModel):
    result: dict[FibreChannelPortAlias, FCPortChoiceEntry] = Field(examples=[
        {
            'fc0': {
                'wwpn': 'naa.2100001122334455',
                'wwpn_b': 'naa.210000AABBCCDDEEFF'
            },
            'fc0/1': {
                'wwpn': 'naa.2200001122334455',
                'wwpn_b': 'naa.220000AABBCCDDEEFF'
            },
        },
    ])


class FCPortStatusArgs(QueryArgs):
    pass  # FIXME: when QueryArgs has better options.extra support add in with_lun_access


class FCPortStatusResult(BaseModel):
    result: list
