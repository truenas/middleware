from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, IPvAnyAddress, NotRequired, excluded_field

__all__ = [
    'JBOFEntry', 'JBOFCreateArgs', 'JBOFCreateResult', 'JBOFDeleteArgs', 'JBOFDeleteResult', 'JBOFLicensedArgs',
    'JBOFLicensedResult', 'JBOFReapplyConfigArgs', 'JBOFReapplyConfigResult', 'JBOFUpdateArgs', 'JBOFUpdateResult',
]


class JBOFEntry(BaseModel):
    id: int = Field(description="Unique identifier for the JBOF configuration.")
    description: str = Field(default=NotRequired, description="Optional description of the JBOF.")
    mgmt_ip1: IPvAnyAddress = Field(description="IP of first Redfish management interface.")
    mgmt_ip2: IPvAnyAddress = Field(
        default=NotRequired,
        description="Optional IP of second Redfish management interface.",
    )
    mgmt_username: str = Field(description="Redfish administrative username.")
    mgmt_password: Secret[str] = Field(description="Redfish administrative password.")
    index: int = Field(description="Index of the JBOF.  Used to determine data plane IP addresses.")
    uuid: str = Field(description="UUID of the JBOF as reported by the enclosure firmware.")


class JBOFCreate(JBOFEntry):
    id: Excluded = excluded_field()
    index: Excluded = excluded_field()
    uuid: Excluded = excluded_field()


class JBOFUpdate(JBOFCreate, metaclass=ForUpdateMetaclass):
    pass


class JBOFCreateArgs(BaseModel):
    data: JBOFCreate = Field(description="JBOF configuration data for creation.")


class JBOFCreateResult(BaseModel):
    result: JBOFEntry = Field(description="The created JBOF configuration.")


class JBOFDeleteArgs(BaseModel):
    id: int = Field(description="ID of the JBOF to delete.")
    force: bool = Field(default=False, description="Whether to force deletion even if the JBOF is in use.")


class JBOFDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the JBOF is successfully deleted.")


class JBOFLicensedArgs(BaseModel):
    pass


class JBOFLicensedResult(BaseModel):
    result: int = Field(description="Number of JBOF units licensed.")


class JBOFReapplyConfigArgs(BaseModel):
    pass


class JBOFReapplyConfigResult(BaseModel):
    result: None = Field(description="Returns `null` when the JBOF configuration is successfully reapplied.")


class JBOFUpdateArgs(BaseModel):
    id: int = Field(description="ID of the JBOF to update.")
    data: JBOFUpdate = Field(description="Updated JBOF configuration data.")


class JBOFUpdateResult(BaseModel):
    result: JBOFEntry = Field(description="The updated JBOF configuration.")
