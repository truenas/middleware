from middlewared.api.base import BaseModel

from pydantic import Field


class InterfaceListenServicesRestartedOnSyncEntry(BaseModel):
    type_: str = Field(alias='type')
    service: str
    ips: list[str]


class InterfaceListenServicesRestartedOnSyncResult(BaseModel):
    result: list[InterfaceListenServicesRestartedOnSyncEntry]


class InterfaceListenServicesRestartedOnSyncArgs(BaseModel):
    pass
