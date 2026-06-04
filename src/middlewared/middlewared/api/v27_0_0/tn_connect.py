from typing import Any, Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    ForUpdateMetaclass,
    HttpsOnlyURL,
    NonEmptyString,
)

__all__ = [
    'TrueNASConnectEntry', 'TrueNASConnectGetRegistrationUriArgs',
    'TrueNASConnectGetRegistrationUriResult',
    'TrueNASConnectUpdate', 'TrueNASConnectUpdateArgs', 'TrueNASConnectUpdateResult',
    'TrueNASConnectGenerateClaimTokenArgs',
    'TrueNASConnectGenerateClaimTokenResult',
    'TrueNASConnectConfigChangedEvent',
    'TrueNASConnectIpsWithHostnamesArgs', 'TrueNASConnectIpsWithHostnamesResult',
]


class TrueNASConnectEntry(BaseModel):
    id: int = Field(description="Unique identifier for the TrueNAS Connect configuration.")
    enabled: bool = Field(description="Whether TrueNAS Connect service is enabled.")
    registration_details: dict[str, Any] = Field(
        description="Object containing registration information and credentials for TrueNAS Connect.",
    )
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
    tier: Literal['FOUNDATION', 'PLUS', 'BUSINESS'] | None = Field(description="TrueNAS Connect tier.")
    last_heartbeat_failure_datetime: str | None = Field(
        description=(
            "Datetime of when the current heartbeat failure streak began. Null if heartbeat is not currently failing."
        ),
    )


class TrueNASConnectUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool = Field(description="Whether to enable the TrueNAS Connect service.")


class TrueNASConnectUpdateArgs(BaseModel):
    tn_connect_update: TrueNASConnectUpdate = Field(description="Updated TrueNAS Connect configuration.")


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


class TrueNASConnectConfigChangedEvent(BaseModel):
    fields: TrueNASConnectEntry = Field(description="Event data.")


class TrueNASConnectIpsWithHostnamesArgs(BaseModel):
    pass


class TrueNASConnectIpsWithHostnamesResult(BaseModel):
    result: dict[str, str]
