from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, LongString,
    single_argument_args,
)


__all__ = [
    'UPSEntry', 'UPSPortChoicesArgs', 'UPSPortChoicesResult', 'UPSDriverChoicesArgs',
    'UPSDriverChoicesResult', 'UPSUpdateArgs', 'UPSUpdateResult',
]


class UPSEntry(BaseModel):
    powerdown: bool
    """Whether the UPS should power down after completing the shutdown sequence."""
    rmonitor: bool
    """Whether to enable remote monitoring of the UPS status over the network."""
    id: int
    """Unique identifier for the UPS configuration."""
    nocommwarntime: int | None
    """Seconds to wait before warning about communication loss with UPS. `null` for default."""
    remoteport: int = Field(ge=1, le=65535)
    """Network port for communicating with remote UPS monitoring systems."""
    shutdowntimer: int
    """Seconds to wait after initiating shutdown before forcing power off."""
    hostsync: int = Field(ge=0)
    """Maximum seconds to wait for other systems to shutdown before continuing."""
    description: str
    """Human-readable description of this UPS configuration."""
    driver: str
    """UPS driver name that handles communication with the specific UPS hardware model."""
    extrausers: LongString
    """Additional user configurations for UPS monitoring access."""
    identifier: NonEmptyString
    """Unique identifier name for this UPS device within the monitoring system."""
    mode: Literal['MASTER', 'SLAVE']
    """Operating mode.
    * `MASTER` controls the UPS directly
    * `SLAVE` monitors remotely"""
    monpwd: str
    """Password for UPS monitoring authentication."""
    monuser: NonEmptyString
    """Username for UPS monitoring authentication."""
    options: LongString
    """Additional configuration options passed to the UPS driver."""
    optionsupsd: LongString
    """Additional configuration options for the UPS daemon."""
    port: str
    """Serial port or device path for UPS communication."""
    remotehost: str
    """Hostname or IP address of remote UPS server when operating in SLAVE mode."""
    shutdown: Literal['LOWBATT', 'BATT']
    """Shutdown trigger condition: LOWBATT on low battery, BATT when on battery power."""
    shutdowncmd: str | None
    """Custom command to execute during UPS shutdown sequence. `null` for default."""
    complete_identifier: str
    """Complete UPS identifier including hostname for network monitoring."""


@single_argument_args('ups_update')
class UPSUpdateArgs(UPSEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    complete_identifier: Excluded = excluded_field()
    monpwd: NonEmptyString
    """Password for UPS monitoring authentication (required for updates)."""


class UPSUpdateResult(BaseModel):
    result: UPSEntry
    """The updated UPS configuration."""


class UPSPortChoicesArgs(BaseModel):
    pass


class UPSPortChoicesResult(BaseModel):
    result: list[str]
    """Array of available serial ports and device paths for UPS communication."""


class UPSDriverChoicesArgs(BaseModel):
    pass


class UPSDriverChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available UPS driver names and their descriptions."""
