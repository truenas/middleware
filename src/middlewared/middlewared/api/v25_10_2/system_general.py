from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    IPv4Address,
    IPv6Address,
    IPNetwork,
    NonEmptyString,
    single_argument_args,
    TcpPort,
    UniqueList,
)

__all__ = [
    "SystemGeneralEntry", "SystemGeneralUpdateArgs", "SystemGeneralUpdateResult",
    "SystemGeneralCheckinWaitingArgs", "SystemGeneralCheckinWaitingResult",
    "SystemGeneralCheckinArgs", "SystemGeneralCheckinResult",
    'SystemGeneralCountryChoicesArgs',
    'SystemGeneralCountryChoicesResult',
]


class SystemGeneralEntry(BaseModel):
    id: int
    """Unique identifier for the system general configuration."""
    ui_certificate: Secret[dict | None]  # FIXME: Make reference to the certificate model when we move it to new API
    """Used to enable HTTPS access to the system. If `ui_certificate` is not configured on boot, it is automatically \
    created by the system."""
    ui_httpsport: TcpPort
    """HTTPS port for the web UI."""
    ui_httpsredirect: bool
    """When set, makes sure that all HTTP requests are converted to HTTPS requests to better enhance security."""
    ui_httpsprotocols: UniqueList[Literal['TLSv1', 'TLSv1.1', 'TLSv1.2', 'TLSv1.3']]
    """Array of TLS protocol versions enabled for HTTPS connections."""
    ui_port: TcpPort
    """HTTP port for the web UI."""
    ui_address: list[IPv4Address] = Field(min_length=1)
    """A list of valid IPv4 addresses which the system will listen on."""
    ui_v6address: list[IPv6Address] = Field(min_length=1)
    """A list of valid IPv6 addresses which the system will listen on."""
    ui_allowlist: list[IPNetwork]
    """A list of IP addresses and networks that are allow to use API and UI. If this list is empty, then all IP \
    addresses are allowed to use API and UI."""
    ui_consolemsg: bool
    """Whether to show console messages on the web UI."""
    ui_x_frame_options: Literal["SAMEORIGIN", "DENY", "ALLOW_ALL"]
    """X-Frame-Options header policy for web UI security."""
    kbdmap: str
    """System keyboard layout mapping."""
    timezone: NonEmptyString
    """System timezone identifier."""
    usage_collection: bool | None
    """Whether usage data collection is enabled. `null` if not set."""
    wizardshown: bool
    """Whether the initial setup wizard has been shown."""
    usage_collection_is_set: bool
    """Whether the usage collection preference has been explicitly set."""
    ds_auth: bool
    """Controls whether configured Directory Service users that are granted with Privileges are allowed to log in to \
    the Web UI or use TrueNAS API."""


@single_argument_args("general_settings")
class SystemGeneralUpdateArgs(SystemGeneralEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    ui_certificate: Secret[int | None]
    """Used to enable HTTPS access to the system. If `ui_certificate` is not configured on boot, it is automatically \
    created by the system."""
    wizardshown: Excluded = excluded_field()
    usage_collection_is_set: Excluded = excluded_field()
    ui_restart_delay: int | None
    """Delay in seconds before restarting the UI after configuration changes. `null` to use default."""
    rollback_timeout: int | None
    """Timeout in seconds for automatic rollback of UI changes. `null` for no timeout."""


class SystemGeneralUpdateResult(BaseModel):
    result: SystemGeneralEntry
    """The updated system general configuration."""


class SystemGeneralCheckinWaitingArgs(BaseModel):
    pass


class SystemGeneralCheckinWaitingResult(BaseModel):
    result: int | None
    """Seconds remaining until automatic rollback. `null` if no rollback is pending."""


class SystemGeneralCheckinArgs(BaseModel):
    pass


class SystemGeneralCheckinResult(BaseModel):
    result: None
    """Returns `null` on successful configuration check-in."""


class SystemGeneralCountryChoicesArgs(BaseModel):
    pass


class SystemGeneralCountryChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of country codes and their names."""
