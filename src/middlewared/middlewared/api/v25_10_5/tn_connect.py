from pydantic import Field, IPvAnyAddress

from middlewared.api.base import BaseModel, ForUpdateMetaclass, HttpsOnlyURL, NonEmptyString, single_argument_args

__all__ = [
    'TrueNASConnectEntry', 'TrueNASConnectGetRegistrationUriArgs',
    'TrueNASConnectGetRegistrationUriResult',
    'TrueNASConnectUpdateArgs', 'TrueNASConnectUpdateResult',
    'TrueNASConnectGenerateClaimTokenArgs',
    'TrueNASConnectGenerateClaimTokenResult',
    'TrueNASConnectIpChoicesArgs', 'TrueNASConnectIpChoicesResult',
]


class TrueNASConnectEntry(BaseModel):
    id: int = Field(description="Unique identifier for the TrueNAS Connect configuration.")
    enabled: bool = Field(description="Whether TrueNAS Connect service is enabled.")
    registration_details: dict = Field(
        description="Object containing registration information and credentials for TrueNAS Connect.",
    )
    ips: list[NonEmptyString] = Field(
        description="Array of IP addresses that TrueNAS Connect will bind to and advertise.",
    )
    interfaces: list[str] = Field(description="Array of network interface names that TrueNAS Connect will use.")
    interfaces_ips: list[str] = Field(description="Array of IP addresses associated with the selected interfaces.")
    use_all_interfaces: bool = Field(description="Whether to automatically use all available network interfaces.")
    status: NonEmptyString = Field(description="Current operational status of the TrueNAS Connect service.")
    status_reason: NonEmptyString = Field(
        description="Detailed explanation of the current status, including any error conditions.",
    )
    certificate: int | None = Field(
        description="ID of the SSL certificate used for TrueNAS Connect communications. `null` if using default.",
    )
    account_service_base_url: HttpsOnlyURL = Field(description="Base URL for the TrueNAS Connect account service API.")
    leca_service_base_url: HttpsOnlyURL = Field(
        description="Base URL for the Let's Encrypt Certificate Authority service used by TrueNAS Connect.",
    )
    tnc_base_url: HttpsOnlyURL = Field(description="Base URL for the TrueNAS Connect service.")
    heartbeat_url: HttpsOnlyURL = Field(
        description="URL endpoint for sending heartbeat signals to maintain connection status.",
    )


@single_argument_args('tn_connect_update')
class TrueNASConnectUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool = Field(description="Whether to enable the TrueNAS Connect service.")
    ips: list[IPvAnyAddress] = Field(
        description="Array of IP addresses that TrueNAS Connect should bind to and advertise.",
    )
    interfaces: list[str] = Field(description="Array of network interface names that TrueNAS Connect should use.")
    use_all_interfaces: bool = Field(description="Whether to automatically use all available network interfaces.")


class TrueNASConnectUpdateResult(BaseModel):
    result: TrueNASConnectEntry = Field(description="The updated TrueNAS Connect configuration.")


class TrueNASConnectGetRegistrationUriArgs(BaseModel):
    pass


class TrueNASConnectGetRegistrationUriResult(BaseModel):
    result: NonEmptyString = Field(
        description="Registration URI for connecting this TrueNAS system to TrueNAS Connect.",
    )


class TrueNASConnectGenerateClaimTokenArgs(BaseModel):
    pass


class TrueNASConnectGenerateClaimTokenResult(BaseModel):
    result: NonEmptyString = Field(
        description="Generated claim token for authenticating with TrueNAS Connect services.",
    )


class TrueNASConnectIpChoicesArgs(BaseModel):
    pass


class TrueNASConnectIpChoicesResult(BaseModel):
    result: dict[str, str] = Field(
        description="Object of available IP addresses and their associated interface descriptions.",
    )
