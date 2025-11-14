from pydantic import IPvAnyAddress

from middlewared.api.base import BaseModel, ForUpdateMetaclass, HttpsOnlyURL, NonEmptyString, single_argument_args


__all__ = [
    'TrueNASConnectEntry', 'TrueNASConnectGetRegistrationUriArgs',
    'TrueNASConnectGetRegistrationUriResult',
    'TrueNASConnectUpdateArgs', 'TrueNASConnectUpdateResult',
    'TrueNASConnectGenerateClaimTokenArgs',
    'TrueNASConnectGenerateClaimTokenResult',
    'TrueNASConnectIpChoicesArgs', 'TrueNASConnectIpChoicesResult',
    'TrueNASConnectConfigChangedEvent',
]


class TrueNASConnectEntry(BaseModel):
    id: int
    """Unique identifier for the TrueNAS Connect configuration."""
    enabled: bool
    """Whether TrueNAS Connect service is enabled."""
    registration_details: dict
    """Object containing registration information and credentials for TrueNAS Connect."""
    ips: list[NonEmptyString]
    """Array of IP addresses that TrueNAS Connect will bind to and advertise."""
    interfaces: list[str]
    """Array of network interface names that TrueNAS Connect will use."""
    interfaces_ips: list[str]
    """Array of IP addresses associated with the selected interfaces."""
    use_all_interfaces: bool
    """Whether to automatically use all available network interfaces."""
    status: NonEmptyString
    """Current operational status of the TrueNAS Connect service."""
    status_reason: NonEmptyString
    """Detailed explanation of the current status, including any error conditions."""
    certificate: int | None
    """ID of the SSL certificate used for TrueNAS Connect communications. `null` if using default."""
    account_service_base_url: HttpsOnlyURL
    """Base URL for the TrueNAS Connect account service API."""
    leca_service_base_url: HttpsOnlyURL
    """Base URL for the Let's Encrypt Certificate Authority service used by TrueNAS Connect."""
    tnc_base_url: HttpsOnlyURL
    """Base URL for the TrueNAS Connect service."""
    heartbeat_url: HttpsOnlyURL
    """URL endpoint for sending heartbeat signals to maintain connection status."""


@single_argument_args('tn_connect_update')
class TrueNASConnectUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool
    """Whether to enable the TrueNAS Connect service."""
    ips: list[IPvAnyAddress]
    """Array of IP addresses that TrueNAS Connect should bind to and advertise."""
    interfaces: list[str]
    """Array of network interface names that TrueNAS Connect should use."""
    use_all_interfaces: bool
    """Whether to automatically use all available network interfaces."""


class TrueNASConnectUpdateResult(BaseModel):
    result: TrueNASConnectEntry
    """The updated TrueNAS Connect configuration."""


class TrueNASConnectGetRegistrationUriArgs(BaseModel):
    pass


class TrueNASConnectGetRegistrationUriResult(BaseModel):
    result: NonEmptyString
    """Registration URI for connecting this TrueNAS system to TrueNAS Connect."""


class TrueNASConnectGenerateClaimTokenArgs(BaseModel):
    pass


class TrueNASConnectGenerateClaimTokenResult(BaseModel):
    result: NonEmptyString
    """Generated claim token for authenticating with TrueNAS Connect services."""


class TrueNASConnectIpChoicesArgs(BaseModel):
    pass


class TrueNASConnectIpChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available IP addresses and their associated interface descriptions."""


class TrueNASConnectConfigChangedEvent(BaseModel):
    fields: TrueNASConnectEntry
    """Event data."""
