from typing import Literal

from pydantic import Secret

from middlewared.api.base import BaseModel, IPvAnyAddress, Excluded, excluded_field, NotRequired, ForUpdateMetaclass


__all__ = [
    'JBOFEntry', 'JBOFCreateArgs', 'JBOFCreateResult', 'JBOFDeleteArgs', 'JBOFDeleteResult', 'JBOFLicensedArgs',
    'JBOFLicensedResult', 'JBOFReapplyConfigArgs', 'JBOFReapplyConfigResult', 'JBOFUpdateArgs', 'JBOFUpdateResult',
]


class JBOFEntry(BaseModel):
    id: int
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


class JBOFCreateResult(BaseModel):
    result: JBOFEntry


class JBOFDeleteArgs(BaseModel):
    id: int
    force: bool = False


class JBOFDeleteResult(BaseModel):
    result: Literal[True]


class JBOFLicensedArgs(BaseModel):
    pass


class JBOFLicensedResult(BaseModel):
    result: int
    """Number of JBOF units licensed."""


class JBOFReapplyConfigArgs(BaseModel):
    pass


class JBOFReapplyConfigResult(BaseModel):
    result: None


class JBOFUpdateArgs(BaseModel):
    id: int
    data: JBOFUpdate


class JBOFUpdateResult(BaseModel):
    result: JBOFEntry
