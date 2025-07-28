from typing import Literal

from pydantic import Secret

from middlewared.api.base import BaseModel, IPvAnyAddress, Excluded, excluded_field, NotRequired, ForUpdateMetaclass


__all__ = [
    'JBOFEntry', 'JBOFCreateArgs', 'JBOFCreateResult', 'JBOFDeleteArgs', 'JBOFDeleteResult', 'JBOFLicensedArgs',
    'JBOFLicensedResult', 'JBOFReapplyConfigArgs', 'JBOFReapplyConfigResult', 'JBOFUpdateArgs', 'JBOFUpdateResult',
]


class JBOFEntry(BaseModel):
    id: int
    """Unique identifier for the JBOF configuration."""
    description: str = NotRequired
    """Optional description of the JBOF."""
    mgmt_ip1: IPvAnyAddress
    """IP of first Redfish management interface."""
    mgmt_ip2: IPvAnyAddress = NotRequired
    """Optional IP of second Redfish management interface."""
    mgmt_username: str
    """Redfish administrative username."""
    mgmt_password: Secret[str]
    """Redfish administrative password."""
    index: int
    """Index of the JBOF.  Used to determine data plane IP addresses."""
    uuid: str
    """UUID of the JBOF as reported by the enclosure firmware."""


class JBOFCreate(JBOFEntry):
    id: Excluded = excluded_field()
    index: Excluded = excluded_field()
    uuid: Excluded = excluded_field()


class JBOFUpdate(JBOFCreate, metaclass=ForUpdateMetaclass):
    pass


class JBOFCreateArgs(BaseModel):
    data: JBOFCreate
    """JBOF configuration data for creation."""


class JBOFCreateResult(BaseModel):
    result: JBOFEntry
    """The created JBOF configuration."""


class JBOFDeleteArgs(BaseModel):
    id: int
    """ID of the JBOF to delete."""
    force: bool = False
    """Whether to force deletion even if the JBOF is in use."""


class JBOFDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the JBOF is successfully deleted."""


class JBOFLicensedArgs(BaseModel):
    pass


class JBOFLicensedResult(BaseModel):
    result: int
    """Number of JBOF units licensed."""


class JBOFReapplyConfigArgs(BaseModel):
    pass


class JBOFReapplyConfigResult(BaseModel):
    result: None
    """Returns `null` when the JBOF configuration is successfully reapplied."""


class JBOFUpdateArgs(BaseModel):
    id: int
    """ID of the JBOF to update."""
    data: JBOFUpdate
    """Updated JBOF configuration data."""


class JBOFUpdateResult(BaseModel):
    result: JBOFEntry
    """The updated JBOF configuration."""
