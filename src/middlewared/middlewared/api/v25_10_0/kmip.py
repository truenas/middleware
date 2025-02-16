from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args


__all__ = [
    'KMIPEntry', 'KMIPKmipSyncPendingArgs', 'KMIPKmipSyncPendingResult',
    'KMIPSyncKeysArgs', 'KMIPSyncKeysResult', 'KMIPClearSyncPendingKeysArgs',
    'KMIPClearSyncPendingKeysResult', 'KMIPUpdateArgs', 'KMIPUpdateResult'
]


class KMIPEntry(BaseModel):
    id: int
    enabled: bool
    manage_sed_disk: bool
    manage_zfs_keys: bool
    certificate: int | None
    certificate_authority: int | None
    port: int = Field(ge=1, le=65535)
    server: str | None
    ssl_version: Literal['PROTOCOL_TLSv1', 'PROTOCOL_TLSv1_1', 'PROTOCOL_TLSv1_2']


class KMIPKmipSyncPendingArgs(BaseModel):
    pass


class KMIPKmipSyncPendingResult(BaseModel):
    result: bool


class KMIPSyncKeysArgs(BaseModel):
    pass


class KMIPSyncKeysResult(BaseModel):
    result: None


class KMIPClearSyncPendingKeysArgs(BaseModel):
    pass


class KMIPClearSyncPendingKeysResult(BaseModel):
    result: None


@single_argument_args('kmip_update')
class KMIPUpdateArgs(KMIPEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    enabled: bool
    force_clear: bool
    change_server: bool
    validate_: bool = Field(alias='validate')


class KMIPUpdateResult(BaseModel):
    result: KMIPEntry
