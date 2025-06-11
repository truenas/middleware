import enum
from typing import Annotated, Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, ForUpdateMetaclass, single_argument_args


__all__ = [
    'TRUECOMMAND_CONNECTING_STATUS_REASON', 'TruecommandStatus', 'TruecommandStatusReason',
    'TruecommandEntry', 'TruecommandUpdateArgs', 'TruecommandUpdateResult',
]

TRUECOMMAND_CONNECTING_STATUS_REASON = 'Waiting for connection from Truecommand.'


class TruecommandStatus(enum.Enum):
    CONNECTED = 'CONNECTED'
    CONNECTING = 'CONNECTING'
    DISABLED = 'DISABLED'
    FAILED = 'FAILED'

# In the database we save 3 states, CONNECTED/DISABLED/FAILED
# Connected is saved when portal has approved an api key
# Disabled is saved when TC service is disabled
# Failed is saved when portal revokes an api key
#
# We report CONNECTED to the user when we have an active wireguard
# connection with TC which is not failing a health check.
# If portal has not approved the api key yet but has registered it
# we report CONNECTING to the user.
# Connecting is also reported when wireguard connection fails health
# check


class TruecommandStatusReason(enum.Enum):
    CONNECTED = 'Truecommand service is connected.'
    CONNECTING = 'Pending Confirmation From iX Portal for Truecommand API Key.'
    DISABLED = 'Truecommand service is disabled.'
    FAILED = 'Truecommand API Key Disabled by iX Portal.'


class TruecommandEntry(BaseModel):
    id: int
    api_key: Secret[str | None]
    status: Literal[tuple(s.value for s in TruecommandStatus)]
    status_reason: Literal[
        tuple(s.value for s in TruecommandStatusReason) + tuple([TRUECOMMAND_CONNECTING_STATUS_REASON])
    ]
    remote_url: str | None
    remote_ip_address: str | None
    enabled: bool


@single_argument_args('truecommand_update')
class TruecommandUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool
    api_key: Secret[Annotated[str, Field(min_length=16, max_length=16)] | None]


class TruecommandUpdateResult(BaseModel):
    result: TruecommandEntry
