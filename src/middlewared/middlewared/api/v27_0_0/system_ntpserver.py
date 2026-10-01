from typing import Annotated, Literal

from pydantic import Field
from pydantic.types import StringConstraints

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, SingleLineNonEmptyString, excluded_field

__all__ = [
    'NTPServerEntry',
    'NTPServerCreate', 'NTPServerUpdate',
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
    nts: bool = Field(
        default=False,
        description=(
            "Use Network Time Security (NTS) to authenticate this server.\n\n"
            "The server must support NTS key establishment on TCP port 4460. This system must trust the TLS "
            "certificate of the server. The certificate must match `address`. If `address` is an IP address, the "
            "certificate must include that IP address. The system clock must be approximately correct for the "
            "certificate check.\n\n"
            "When at least one NTS server is configured, the system ignores servers without NTS. This includes "
            "servers from DHCP. If no NTS server is reachable, the system does not adjust the clock."
        ),
    )


class NTPServerCreate(NTPServerEntry):
    """A new NTP server.

    The system writes `address` unchanged into a `server` line of `chrony.conf`. chronyd reads that file as root.
    A line break in `address` lets the caller add chrony directives, so `address` must not contain one.
    A space in `address` lets the caller add options to the `server` line, so `address` must not contain one.
    These rules apply to this model and not to `NTPServerEntry`, so that older stored values stay readable.
    """
    id: Excluded = excluded_field()
    address: Annotated[SingleLineNonEmptyString, StringConstraints(pattern=r'^\S+$')]
    force: bool = Field(
        default=False,
        description=(
            "Skip the connection checks before saving. Without this option, the server must be reachable. If `nts` "
            "is set, NTS key establishment with the server must also succeed."
        ),
    )


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
