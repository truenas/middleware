from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass
from typing import Literal


__all__ = [
    'NTPServerEntry',
    'NTPServerCreateArgs', 'NTPServerCreateResult',
    'NTPServerUpdateArgs', 'NTPServerUpdateResult',
    'NTPServerDeleteArgs', 'NTPServerDeleteResult',
]


class NTPServerEntry(BaseModel):
    id: int
    """Unique identifier for the NTP server configuration."""
    address: str
    """Hostname or IP address of the NTP server."""
    burst: bool = False
    """Send a burst of packets when the server is reachable."""
    iburst: bool = True
    """Send a burst of packets when the server is unreachable."""
    prefer: bool = False
    """Mark this server as preferred for time synchronization."""
    minpoll: int = 6
    """Minimum polling interval (log2 seconds)."""
    maxpoll: int = 10
    """Maximum polling interval (log2 seconds)."""


class NTPServerCreate(NTPServerEntry):
    id: Excluded = excluded_field()
    force: bool = False
    """Force creation even if the server is unreachable."""


class NTPServerUpdate(NTPServerCreate, metaclass=ForUpdateMetaclass):
    pass


class NTPServerCreateArgs(BaseModel):
    ntp_server_create: NTPServerCreate
    """Configuration for creating a new NTP server."""


class NTPServerUpdateArgs(BaseModel):
    id: int
    """ID of the NTP server to update."""
    ntp_server_update: NTPServerUpdate
    """Updated configuration for the NTP server."""


class NTPServerCreateResult(BaseModel):
    result: NTPServerEntry
    """The newly created NTP server configuration."""


class NTPServerUpdateResult(BaseModel):
    result: NTPServerEntry
    """The updated NTP server configuration."""


class NTPServerDeleteArgs(BaseModel):
    id: int
    """ID of the NTP server to delete."""


class NTPServerDeleteResult(BaseModel):
    result: Literal[True]
    """Always returns true on successful NTP server deletion."""
