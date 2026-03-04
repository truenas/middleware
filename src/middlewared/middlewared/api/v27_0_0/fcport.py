from typing import Literal

from pydantic import Field

from middlewared.api.base import WWPN, BaseModel, Excluded, FibreChannelPortAlias, ForUpdateMetaclass, excluded_field
from .common import QueryArgs, QueryOptions


__all__ = [
    "FCPortEntry", "FCPortCreateArgs", "FCPortCreateResult", "FCPortUpdateArgs", "FCPortUpdateResult",
    "FCPortDeleteArgs", "FCPortDeleteResult", "FCPortPortChoicesArgs", "FCPortPortChoicesResult", "FCPortStatusArgs",
    "FCPortStatusResult",
]


class FCPortEntry(BaseModel):
    id: int
    """Unique identifier for the Fibre Channel port configuration."""
    port: FibreChannelPortAlias
    """Alias name for the Fibre Channel port."""
    wwpn: WWPN | None
    """World Wide Port Name for port A or `null` if not configured."""
    wwpn_b: WWPN | None
    """World Wide Port Name for port B or `null` if not configured."""
    target: dict | None
    """Target configuration object or `null` if not configured."""


class FCPortCreate(FCPortEntry):
    id: Excluded = excluded_field()
    wwpn: Excluded = excluded_field()
    wwpn_b: Excluded = excluded_field()
    target: Excluded = excluded_field()
    target_id: int
    """ID of the target to associate with this FC port."""


class FCPortCreateArgs(BaseModel):
    fc_Port_create: FCPortCreate
    """Fibre Channel port configuration data for the new port."""


class FCPortCreateResult(BaseModel):
    result: FCPortEntry
    """The created Fibre Channel port configuration."""


class FCPortUpdate(FCPortCreate, metaclass=ForUpdateMetaclass):
    pass


class FCPortUpdateArgs(BaseModel):
    id: int
    """ID of the Fibre Channel port to update."""
    fc_Port_update: FCPortUpdate
    """Updated Fibre Channel port configuration data."""


class FCPortUpdateResult(BaseModel):
    result: FCPortEntry
    """The updated Fibre Channel port configuration."""


class FCPortDeleteArgs(BaseModel):
    id: int
    """ID of the Fibre Channel port to delete."""


class FCPortDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the Fibre Channel port is successfully deleted."""


class FCPortChoiceEntry(BaseModel):
    wwpn: WWPN | None
    """World Wide Port Name for port A or `null` if not available."""
    wwpn_b: WWPN | None
    """World Wide Port Name for port B or `null` if not available."""


class FCPortPortChoicesArgs(BaseModel):
    include_used: bool = True
    """Whether to include FC ports that are already in use."""


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


class FCPortStatusOptionsExtra(BaseModel):
    with_lun_access: bool = True
    """When `true`, only include Fibre Channel sessions that have access to at least one LUN (Logical Unit Number). \
    When `false`, include all Fibre Channel sessions regardless of LUN access."""


class FCPortStatusOptions(QueryOptions):
    extra: FCPortStatusOptionsExtra = FCPortStatusOptionsExtra()


class FCPortStatusArgs(QueryArgs):
    options: FCPortStatusOptions = FCPortStatusOptions()


class FCPortStatusResult(BaseModel):
    result: list
    """Array of Fibre Channel port status information."""
