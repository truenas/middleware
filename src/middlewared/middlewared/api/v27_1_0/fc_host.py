from typing import Literal

from pydantic import Field

from middlewared.api.base import WWPN, BaseModel, Excluded, FibreChannelHostAlias, ForUpdateMetaclass, excluded_field


__all__ = [
    "FCHostEntry", "FCHostCreateArgs", "FCHostCreateResult", "FCHostUpdateArgs", "FCHostUpdateResult",
    "FCHostDeleteArgs", "FCHostDeleteResult",
]


class FCHostEntry(BaseModel):
    id: int = Field(description="Unique identifier for the Fibre Channel host configuration.")
    alias: FibreChannelHostAlias = Field(description="Human-readable alias for the Fibre Channel host.")
    wwpn: WWPN | None = Field(default=None, description="World Wide Port Name for port A or `null` if not configured.")
    wwpn_b: WWPN | None = Field(
        default=None,
        description="World Wide Port Name for port B or `null` if not configured.",
    )
    npiv: int = Field(default=0, description="Number of N_Port ID Virtualization (NPIV) virtual ports to create.")


class FCHostCreate(FCHostEntry):
    id: Excluded = excluded_field()


class FCHostCreateArgs(BaseModel):
    fc_host_create: FCHostCreate = Field(description="Fibre Channel host configuration data for the new host.")


class FCHostCreateResult(BaseModel):
    result: FCHostEntry = Field(description="The created Fibre Channel host configuration.")


class FCHostUpdate(FCHostCreate, metaclass=ForUpdateMetaclass):
    pass


class FCHostUpdateArgs(BaseModel):
    id: int = Field(description="ID of the Fibre Channel host to update.")
    fc_host_update: FCHostUpdate = Field(description="Updated Fibre Channel host configuration data.")


class FCHostUpdateResult(BaseModel):
    result: FCHostEntry = Field(description="The updated Fibre Channel host configuration.")


class FCHostDeleteArgs(BaseModel):
    id: int = Field(description="ID of the Fibre Channel host to delete.")


class FCHostDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the Fibre Channel host is successfully deleted.")
