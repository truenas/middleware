from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass
from typing import Literal


__all__ = [
    'NTPServerEntry',
    'NTPServerCreateArgs', 'NTPServerCreateResult',
    'NTPServerUpdateArgs', 'NTPServerUpdateResult',
    'NTPServerDeleteArgs', 'NTPServerDeleteResult',
]


class NTPServerEntry(BaseModel):
    id: int = Field(description="Unique identifier for the NTP server configuration.")
    address: str = Field(description="Hostname or IP address of the NTP server.")
    burst: bool = Field(default=False, description="Send a burst of packets when the server is reachable.")
    iburst: bool = Field(default=True, description="Send a burst of packets when the server is unreachable.")
    prefer: bool = Field(default=False, description="Mark this server as preferred for time synchronization.")
    minpoll: int = Field(default=6, description="Minimum polling interval (log2 seconds).")
    maxpoll: int = Field(default=10, description="Maximum polling interval (log2 seconds).")


class NTPServerCreate(NTPServerEntry):
    id: Excluded = excluded_field()
    force: bool = Field(default=False, description="Force creation even if the server is unreachable.")


class NTPServerUpdate(NTPServerCreate, metaclass=ForUpdateMetaclass):
    pass


class NTPServerCreateArgs(BaseModel):
    ntp_server_create: NTPServerCreate = Field(description="Configuration for creating a new NTP server.")


class NTPServerUpdateArgs(BaseModel):
    id: int = Field(description="ID of the NTP server to update.")
    ntp_server_update: NTPServerUpdate = Field(description="Updated configuration for the NTP server.")


class NTPServerCreateResult(BaseModel):
    result: NTPServerEntry = Field(description="The newly created NTP server configuration.")


class NTPServerUpdateResult(BaseModel):
    result: NTPServerEntry = Field(description="The updated NTP server configuration.")


class NTPServerDeleteArgs(BaseModel):
    id: int = Field(description="ID of the NTP server to delete.")


class NTPServerDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Always returns true on successful NTP server deletion.")
