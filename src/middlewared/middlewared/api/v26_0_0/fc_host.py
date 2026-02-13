from typing import Literal

from middlewared.api.base import WWPN, BaseModel, Excluded, FibreChannelHostAlias, ForUpdateMetaclass, excluded_field


__all__ = [
    "FCHostEntry", "FCHostCreateArgs", "FCHostCreateResult", "FCHostUpdateArgs", "FCHostUpdateResult",
    "FCHostDeleteArgs", "FCHostDeleteResult",
]


class FCHostEntry(BaseModel):
    id: int
    """Unique identifier for the Fibre Channel host configuration."""
    alias: FibreChannelHostAlias
    """Human-readable alias for the Fibre Channel host."""
    wwpn: WWPN | None = None
    """World Wide Port Name for port A or `null` if not configured."""
    wwpn_b: WWPN | None = None
    """World Wide Port Name for port B or `null` if not configured."""
    npiv: int = 0
    """Number of N_Port ID Virtualization (NPIV) virtual ports to create."""


class FCHostCreate(FCHostEntry):
    id: Excluded = excluded_field()


class FCHostCreateArgs(BaseModel):
    fc_host_create: FCHostCreate
    """Fibre Channel host configuration data for the new host."""


class FCHostCreateResult(BaseModel):
    result: FCHostEntry
    """The created Fibre Channel host configuration."""


class FCHostUpdate(FCHostCreate, metaclass=ForUpdateMetaclass):
    pass


class FCHostUpdateArgs(BaseModel):
    id: int
    """ID of the Fibre Channel host to update."""
    fc_host_update: FCHostUpdate
    """Updated Fibre Channel host configuration data."""


class FCHostUpdateResult(BaseModel):
    result: FCHostEntry
    """The updated Fibre Channel host configuration."""


class FCHostDeleteArgs(BaseModel):
    id: int
    """ID of the Fibre Channel host to delete."""


class FCHostDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the Fibre Channel host is successfully deleted."""
