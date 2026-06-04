from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    excluded_field,
    single_argument_args,
)

__all__ = [
    'KMIPEntry', 'KMIPKmipSyncPendingArgs', 'KMIPKmipSyncPendingResult',
    'KMIPSyncKeysArgs', 'KMIPSyncKeysResult', 'KMIPClearSyncPendingKeysArgs',
    'KMIPClearSyncPendingKeysResult', 'KMIPUpdateArgs', 'KMIPUpdateResult'
]


class KMIPEntry(BaseModel):
    id: int = Field(description="Unique identifier for the KMIP configuration.")
    enabled: bool = Field(description="Whether KMIP (Key Management Interoperability Protocol) is enabled.")
    manage_sed_disks: bool = Field(description="Whether to use KMIP for managing SED (Self-Encrypting Drive) keys.")
    manage_zfs_keys: bool = Field(description="Whether to use KMIP for managing ZFS encryption keys.")
    certificate: int | None = Field(description="ID of the client certificate for KMIP authentication or `null`.")
    certificate_authority: int | None = Field(
        description="ID of the certificate authority for server verification or `null`.",
    )
    port: int = Field(ge=1, le=65535, description="TCP port number for the KMIP server connection.")
    server: NonEmptyString | None = Field(
        description="Hostname or IP address of the KMIP server or `null` if not configured.",
    )
    ssl_version: Literal['PROTOCOL_TLSv1', 'PROTOCOL_TLSv1_1', 'PROTOCOL_TLSv1_2'] = Field(
        description="SSL/TLS protocol version to use for KMIP connections.",
    )


@single_argument_args('kmip_update')
class KMIPUpdateArgs(KMIPEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    enabled: bool = Field(description="Whether to enable KMIP functionality.")
    force_clear: bool = Field(description="Whether to force clear existing keys when disabling KMIP.")
    change_server: bool = Field(description="Whether the KMIP server configuration is being changed.")
    validate_: bool = Field(
        alias='validate',
        description="Whether to validate the KMIP server connection before saving.",
    )


class KMIPUpdateResult(BaseModel):
    result: KMIPEntry = Field(description="The updated KMIP configuration.")


class KMIPKmipSyncPendingArgs(BaseModel):
    pass


class KMIPKmipSyncPendingResult(BaseModel):
    result: bool = Field(description="Returns `true` if there are keys pending synchronization with the KMIP server.")


class KMIPSyncKeysArgs(BaseModel):
    pass


class KMIPSyncKeysResult(BaseModel):
    result: None = Field(description="Returns `null` when key synchronization with the KMIP server completes.")


class KMIPClearSyncPendingKeysArgs(BaseModel):
    pass


class KMIPClearSyncPendingKeysResult(BaseModel):
    result: None = Field(description="Returns `null` when pending sync keys are successfully cleared.")
