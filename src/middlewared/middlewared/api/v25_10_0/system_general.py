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
    ui_certificate: Secret[dict | None]  # FIXME: Make reference to the certificate model when we move it to new API
    "Used to enable HTTPS access to the system. If `ui_certificate` is not configured on boot, it is automatically "
    "created by the system."
    ui_httpsport: TcpPort
    ui_httpsredirect: bool
    "When set, makes sure that all HTTP requests are converted to HTTPS requests to better enhance security."
    ui_httpsprotocols: UniqueList[Literal['TLSv1', 'TLSv1.1', 'TLSv1.2', 'TLSv1.3']]
    ui_port: TcpPort
    ui_address: list[IPv4Address] = Field(min_length=1)
    "A list of valid IPv4 addresses which the system will listen on."
    ui_v6address: list[IPv6Address] = Field(min_length=1)
    "A list of valid IPv6 addresses which the system will listen on."
    ui_allowlist: list[IPNetwork]
    "A list of IP addresses and networks that are allow to use API and UI. If this list is empty, then all IP "
    "addresses are allowed to use API and UI."
    ui_consolemsg: bool
    ui_x_frame_options: Literal["SAMEORIGIN", "DENY", "ALLOW_ALL"]
    kbdmap: str
    timezone: NonEmptyString
    usage_collection: bool | None
    wizardshown: bool
    usage_collection_is_set: bool
    ds_auth: bool
    "Controls whether configured Directory Service users that are granted with Privileges are allowed to log in to the "
    "Web UI or use TrueNAS API."


@single_argument_args("general_settings")
class SystemGeneralUpdateArgs(SystemGeneralEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    ui_certificate: Secret[int | None]
    "Used to enable HTTPS access to the system. If `ui_certificate` is not configured on boot, it is automatically "
    "created by the system."
    wizardshown: Excluded = excluded_field()
    usage_collection_is_set: Excluded = excluded_field()
    ui_restart_delay: int | None
    rollback_timeout: int | None


class SystemGeneralUpdateResult(BaseModel):
    result: SystemGeneralEntry


class SystemGeneralCheckinWaitingArgs(BaseModel):
    pass


class SystemGeneralCheckinWaitingResult(BaseModel):
    result: int | None


class SystemGeneralCheckinArgs(BaseModel):
    pass


class SystemGeneralCheckinResult(BaseModel):
    result: None


class SystemGeneralCountryChoicesArgs(BaseModel):
    pass


class SystemGeneralCountryChoicesResult(BaseModel):
    result: dict[str, str]
