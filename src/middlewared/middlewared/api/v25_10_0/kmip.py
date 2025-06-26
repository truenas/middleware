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
    enabled: bool
    manage_sed_disks: bool
    manage_zfs_keys: bool
    certificate: int | None
    certificate_authority: int | None
    port: int = Field(ge=1, le=65535)
    server: NonEmptyString | None
    ssl_version: Literal['PROTOCOL_TLSv1', 'PROTOCOL_TLSv1_1', 'PROTOCOL_TLSv1_2']


@single_argument_args('kmip_update')
class KMIPUpdateArgs(KmipEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    enabled: bool
    force_clear: bool
    change_server: bool
    validate_: bool = Field(alias='validate')


class KMIPUpdateResult(BaseModel):
    result: KmipEntry


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
