from typing import Literal

from pydantic import IPvAnyAddress, field_validator

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString

__all__ = [
    "IscsiPortalEntry",
    "ISCSIPortalListenIpChoicesArgs",
    "ISCSIPortalListenIpChoicesResult",
    "ISCSIPortalCreateArgs",
    "ISCSIPortalCreateResult",
    "ISCSIPortalUpdateArgs",
    "ISCSIPortalUpdateResult",
    "ISCSIPortalDeleteArgs",
    "ISCSIPortalDeleteResult",
]


class IscsiPortalIP(BaseModel):
    ip: NonEmptyString
    """IP address for the iSCSI portal to listen on."""

    @field_validator('ip')
    @classmethod
    def check_ip(cls, v):
        IPvAnyAddress(v)
        return v


class IscsiPortalIPInfo(IscsiPortalIP):
    port: int
    """TCP port number for the iSCSI portal."""


class IscsiPortalEntry(BaseModel):
    id: int
    """Unique identifier for the iSCSI portal."""
    listen: list[IscsiPortalIPInfo]
    """Array of IP address and port combinations for the portal to listen on."""
    tag: int
    """Numeric tag used to associate this portal with iSCSI targets."""
    comment: str = ''
    """Optional comment describing the portal."""


class ISCSIPortalListenIpChoicesArgs(BaseModel):
    pass


class ISCSIPortalListenIpChoicesResult(BaseModel):
    result: dict[str, str]
    """Object mapping IP addresses to their underlying constituents. Only static IP addresses will be included. On \
    ALUA-enabled high availability systems, VIPs will be mapped to the pair of corresponding underlying addresses, one \
    per node."""


class IscsiPortalCreate(IscsiPortalEntry):
    id: Excluded = excluded_field()
    tag: Excluded = excluded_field()
    listen: list[IscsiPortalIP]
    """Array of IP addresses for the portal to listen on."""


class ISCSIPortalCreateArgs(BaseModel):
    iscsi_portal_create: IscsiPortalCreate
    """iSCSI portal configuration data for creation."""


class ISCSIPortalCreateResult(BaseModel):
    result: IscsiPortalEntry
    """The created iSCSI portal configuration."""


class IscsiPortalUpdate(IscsiPortalCreate, metaclass=ForUpdateMetaclass):
    pass


class ISCSIPortalUpdateArgs(BaseModel):
    id: int
    """ID of the iSCSI portal to update."""
    iscsi_portal_update: IscsiPortalUpdate
    """Updated iSCSI portal configuration data."""


class ISCSIPortalUpdateResult(BaseModel):
    result: IscsiPortalEntry
    """The updated iSCSI portal configuration."""


class ISCSIPortalDeleteArgs(BaseModel):
    id: int
    """ID of the iSCSI portal to delete."""


class ISCSIPortalDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the iSCSI portal is successfully deleted."""
