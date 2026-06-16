from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    excluded_field,
)

__all__ = [
    'KMIPEntry', 'KMIPUpdate', 'KMIPKmipSyncPendingArgs', 'KMIPKmipSyncPendingResult',
    'KMIPSyncKeysArgs', 'KMIPSyncKeysResult', 'KMIPClearSyncPendingKeysArgs',
    'KMIPClearSyncPendingKeysResult', 'KMIPUpdateArgs', 'KMIPUpdateResult'
]


class KMIPEntry(BaseModel):
    id: int = Field(description="Unique identifier for the KMIP configuration.")
    enabled: bool = Field(description="Whether KMIP (Key Management Interoperability Protocol) is enabled.")
    manage_sed_disks: bool = Field(
        description="Whether to use KMIP for managing SED (Self-Encrypting Drive) keys. When enabled, SED keys "
                    "are synced from the local database to the remote KMIP server. When disabled, any SED keys "
                    "still held on the KMIP server are synced back to the local database."
    )
    manage_zfs_keys: bool = Field(
        description="Whether to use KMIP for managing ZFS encryption keys. When enabled, ZFS keys are synced from "
                    "the local database to the remote KMIP server. When disabled, any ZFS keys still held on the "
                    "KMIP server are synced back to the local database."
    )
    certificate: int | None = Field(
        description="ID of the client certificate used to initiate the TLS handshake with the KMIP `server`, "
                    "or `null`.",
    )
    certificate_authority: int | None = Field(
        description="ID of the certificate authority used to verify the KMIP `server` during the TLS handshake, "
                    "or `null`.",
    )
    port: int = Field(ge=1, le=65535, description="TCP port number for the KMIP server connection.")
    server: NonEmptyString | None = Field(
        description="Hostname or IP address of the KMIP server or `null` if not configured.",
    )
    ssl_version: Literal['PROTOCOL_TLSv1', 'PROTOCOL_TLSv1_1', 'PROTOCOL_TLSv1_2'] = Field(
        description="SSL/TLS protocol version to use for KMIP connections. Specify this to match the SSL "
                    "configuration used by the KMIP server.",
    )


class KMIPUpdate(KMIPEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    enabled: bool = Field(
        description="Whether to enable KMIP functionality. Cannot be set to disabled while there are keys pending "
                    "sync, unless `force_clear` is also set."
    )
    force_clear: bool = Field(
        description="When enabled, removes all keys pending sync from the database. Use with extreme caution: ZFS "
                    "dataset or SED disk keys may be lost, leaving them locked forever. Disabled by default."
    )
    change_server: bool = Field(
        description="Allows migrating data between two KMIP servers. The system first migrates keys from the old "
                    "server to the local database, then from the database to the new server. If it cannot retrieve "
                    "all keys from the old server the operation fails, which can be bypassed with `force_clear`."
    )
    validate_: bool = Field(
        alias='validate',
        description="When enabled (the default), the system tests the connection to `server` to make sure it is "
                    "reachable before saving.",
    )


class KMIPUpdateArgs(BaseModel):
    kmip_update: KMIPUpdate = Field(description="KMIP configuration update arguments.")


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
