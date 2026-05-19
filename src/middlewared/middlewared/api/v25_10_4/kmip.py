from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)

__all__ = [
    'KmipEntry', 'KMIPKmipSyncPendingArgs', 'KMIPKmipSyncPendingResult',
    'KMIPSyncKeysArgs', 'KMIPSyncKeysResult', 'KMIPClearSyncPendingKeysArgs',
    'KMIPClearSyncPendingKeysResult', 'KMIPUpdateArgs', 'KMIPUpdateResult'
]


class KmipEntry(BaseModel):
    id: int
    """Unique identifier for the KMIP configuration."""
    enabled: bool
    """Whether KMIP (Key Management Interoperability Protocol) is enabled."""
    manage_sed_disks: bool
    """Whether to use KMIP for managing SED (Self-Encrypting Drive) keys."""
    manage_zfs_keys: bool
    """Whether to use KMIP for managing ZFS encryption keys."""
    certificate: int | None
    """ID of the client certificate for KMIP authentication or `null`."""
    certificate_authority: int | None
    """ID of the certificate authority for server verification or `null`."""
    port: int = Field(ge=1, le=65535)
    """TCP port number for the KMIP server connection."""
    server: NonEmptyString | None
    """Hostname or IP address of the KMIP server or `null` if not configured."""
    ssl_version: Literal['PROTOCOL_TLSv1', 'PROTOCOL_TLSv1_1', 'PROTOCOL_TLSv1_2']
    """SSL/TLS protocol version to use for KMIP connections."""


@single_argument_args('kmip_update')
class KMIPUpdateArgs(KmipEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    enabled: bool
    """Whether to enable KMIP functionality."""
    force_clear: bool
    """Whether to force clear existing keys when disabling KMIP."""
    change_server: bool
    """Whether the KMIP server configuration is being changed."""
    validate_: bool = Field(alias='validate')
    """Whether to validate the KMIP server connection before saving."""


class KMIPUpdateResult(BaseModel):
    result: KmipEntry
    """The updated KMIP configuration."""


class KMIPKmipSyncPendingArgs(BaseModel):
    pass


class KMIPKmipSyncPendingResult(BaseModel):
    result: bool
    """Returns `true` if there are keys pending synchronization with the KMIP server."""


class KMIPSyncKeysArgs(BaseModel):
    pass


class KMIPSyncKeysResult(BaseModel):
    result: None
    """Returns `null` when key synchronization with the KMIP server completes."""


class KMIPClearSyncPendingKeysArgs(BaseModel):
    pass


class KMIPClearSyncPendingKeysResult(BaseModel):
    result: None
    """Returns `null` when pending sync keys are successfully cleared."""
