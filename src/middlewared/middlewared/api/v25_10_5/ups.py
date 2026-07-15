from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    LongString,
    NonEmptyString,
    excluded_field,
    single_argument_args,
)

__all__ = [
    'UPSEntry', 'UPSPortChoicesArgs', 'UPSPortChoicesResult', 'UPSDriverChoicesArgs',
    'UPSDriverChoicesResult', 'UPSUpdateArgs', 'UPSUpdateResult',
]


class UPSEntry(BaseModel):
    powerdown: bool = Field(description="Whether the UPS should power down after completing the shutdown sequence.")
    rmonitor: bool = Field(description="Whether to enable remote monitoring of the UPS status over the network.")
    id: int = Field(description="Unique identifier for the UPS configuration.")
    nocommwarntime: int | None = Field(
        description="Seconds to wait before warning about communication loss with UPS. `null` for default.",
    )
    remoteport: int = Field(
        ge=1,
        le=65535,
        description="Network port for communicating with remote UPS monitoring systems.",
    )
    shutdowntimer: int = Field(description="Seconds to wait after initiating shutdown before forcing power off.")
    hostsync: int = Field(ge=0, description="Maximum seconds to wait for other systems to shutdown before continuing.")
    description: str = Field(description="Human-readable description of this UPS configuration.")
    driver: str = Field(description="UPS driver name that handles communication with the specific UPS hardware model.")
    extrausers: LongString = Field(description="Additional user configurations for UPS monitoring access.")
    identifier: NonEmptyString = Field(
        description="Unique identifier name for this UPS device within the monitoring system.",
    )
    mode: Literal['MASTER', 'SLAVE'] = Field(
        description=(
            "Operating mode.\n"
            "* `MASTER` controls the UPS directly\n"
            "* `SLAVE` monitors remotely"
        ),
    )
    monpwd: str = Field(description="Password for UPS monitoring authentication.")
    monuser: NonEmptyString = Field(description="Username for UPS monitoring authentication.")
    options: LongString = Field(description="Additional configuration options passed to the UPS driver.")
    optionsupsd: LongString = Field(description="Additional configuration options for the UPS daemon.")
    port: str = Field(description="Serial port or device path for UPS communication.")
    remotehost: str = Field(description="Hostname or IP address of remote UPS server when operating in SLAVE mode.")
    shutdown: Literal['LOWBATT', 'BATT'] = Field(
        description="Shutdown trigger condition: LOWBATT on low battery, BATT when on battery power.",
    )
    shutdowncmd: str | None = Field(
        description="Custom command to execute during UPS shutdown sequence. `null` for default.",
    )
    complete_identifier: str = Field(description="Complete UPS identifier including hostname for network monitoring.")


@single_argument_args('ups_update')
class UPSUpdateArgs(UPSEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    complete_identifier: Excluded = excluded_field()
    monpwd: NonEmptyString = Field(description="Password for UPS monitoring authentication (required for updates).")


class UPSUpdateResult(BaseModel):
    result: UPSEntry = Field(description="The updated UPS configuration.")


class UPSPortChoicesArgs(BaseModel):
    pass


class UPSPortChoicesResult(BaseModel):
    result: list[str] = Field(description="Array of available serial ports and device paths for UPS communication.")


class UPSDriverChoicesArgs(BaseModel):
    pass


class UPSDriverChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Object of available UPS driver names and their descriptions.")
