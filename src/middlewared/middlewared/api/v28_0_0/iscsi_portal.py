from typing import Literal

from pydantic import Field, IPvAnyAddress, field_validator

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

__all__ = [
    "ISCSIPortalEntry",
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
    ip: NonEmptyString = Field(description="IP address for the iSCSI portal to listen on.")

    @field_validator('ip')
    @classmethod
    def check_ip(cls, v):
        IPvAnyAddress(v)
        return v


class IscsiPortalIPInfo(IscsiPortalIP):
    port: int = Field(description="TCP port number for the iSCSI portal.")


class ISCSIPortalEntry(BaseModel):
    id: int = Field(description="Unique identifier for the iSCSI portal.")
    listen: list[IscsiPortalIPInfo] = Field(
        description="Array of IP address and port combinations for the portal to listen on.",
    )
    tag: int = Field(description="Numeric tag used to associate this portal with iSCSI targets.")
    comment: str = Field(default='', description="Optional comment describing the portal.")


class ISCSIPortalListenIpChoicesArgs(BaseModel):
    pass


class ISCSIPortalListenIpChoicesResult(BaseModel):
    result: dict[str, str] = Field(
        description=(
            "Object mapping IP addresses to their underlying constituents. Only static IP addresses will be included. "
            "On ALUA-enabled high availability systems, VIPs will be mapped to the pair of corresponding underlying "
            "addresses, one per node."
        ),
    )


class IscsiPortalCreate(ISCSIPortalEntry):
    id: Excluded = excluded_field()
    tag: Excluded = excluded_field()
    listen: list[IscsiPortalIP] = Field(description="Array of IP addresses for the portal to listen on.")


class ISCSIPortalCreateArgs(BaseModel):
    iscsi_portal_create: IscsiPortalCreate = Field(description="iSCSI portal configuration data for creation.")


class ISCSIPortalCreateResult(BaseModel):
    result: ISCSIPortalEntry = Field(description="The created iSCSI portal configuration.")


class IscsiPortalUpdate(IscsiPortalCreate, metaclass=ForUpdateMetaclass):
    pass


class ISCSIPortalUpdateArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI portal to update.")
    iscsi_portal_update: IscsiPortalUpdate = Field(description="Updated iSCSI portal configuration data.")


class ISCSIPortalUpdateResult(BaseModel):
    result: ISCSIPortalEntry = Field(description="The updated iSCSI portal configuration.")


class ISCSIPortalDeleteArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI portal to delete.")


class ISCSIPortalDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the iSCSI portal is successfully deleted.")
