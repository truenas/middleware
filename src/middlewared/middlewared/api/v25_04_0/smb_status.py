from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    query_result,
)
from pydantic import Field
from typing import Literal
from .common import QueryFilters, QueryOptions

__all__ = ['SmbStatusArgs', 'SmbStatusResult']

EMPTY_STRING = ''
DISABLED = '-'
UNKNOWN = '???'

SmbStatusInformationType = Literal['ALL', 'SESSIONS', 'SHARES', 'LOCKS', 'NOTIFICATIONS']

SmbEncryptionCipher = Literal[DISABLED, 'AES-128-CCM', 'AES-128-GCM', 'AES-256-CCM', 'AES-256-GCM', UNKNOWN]
SmbSigningCipher = Literal[DISABLED, 'HMAC-MD5', 'HMAC-SHA256', 'AES-128-CMAC', 'AES-128-GMAC', UNKNOWN]
SmbCryptoDegree = Literal['none', 'full', 'partial', 'anonymous']


class SmbStatusEncrypt(BaseModel):
    cipher: SmbEncryptionCipher
    degree: SmbCryptoDegree


class SmbStatusSign(BaseModel):
    cipher: SmbSigningCipher
    degree: SmbCryptoDegree


class SmbServerId(BaseModel):
    pid: NonEmptyString
    task_id: NonEmptyString
    vnn: NonEmptyString
    unique_id: NonEmptyString


class SmbOpenFileShareMode(BaseModel):
    hex_str: NonEmptyString = Field(alias='hex')
    text: NonEmptyString
    READ: bool
    WRITE: bool
    DELETE: bool


class SmbOpenFileAccessMask(BaseModel):
    hex_str: NonEmptyString = Field(alias='hex')
    text: NonEmptyString
    READ_DATA: bool
    WRITE_DATA: bool
    APPEND_DATA: bool
    READ_EA: bool
    WRITE_EA: bool
    EXECUTE: bool
    READ_ATTRIBUTES: bool
    WRITE_ATTRIBUTES: bool
    DELETE_CHILD: bool
    DELETE: bool
    READ_CONTROL: bool
    WRITE_DAC: bool
    SYNCHRONIZE: bool
    ACCESS_SYSTEM_SECURITY: bool


class SmbOpenFileCaching(BaseModel):
    hex_str: NonEmptyString = Field(alias='hex')
    text: NonEmptyString
    READ: bool
    WRITE: bool
    HANDLE: bool


class SmbOpenFileOplock(BaseModel):
    hex_str: NonEmptyString = Field(alias='hex')
    text: NonEmptyString
    EXCLUSIVE: bool
    BATCH: bool
    LEVEL_II: bool
    LEASE: bool


class SmbOpenFileLease(BaseModel):
    lease_key: NonEmptyString
    hex_str: NonEmptyString = Field(alias='hex')
    text: NonEmptyString
    READ: bool
    WRITE: bool
    HANDLE: bool


class SmbServerChannel(BaseModel):
    channel_id: NonEmptyString
    creation_time: NonEmptyString
    local_address: NonEmptyString
    remote_address: NonEmptyString


class SmbOpenFileId(BaseModel):
    devid: int
    inode: int
    extid: int


class ShareEntry:
    service: NonEmptyString
    server_id: SmbServerId
    tcon_id: NonEmptyString
    session_id: NonEmptyString
    machine: NonEmptyString
    connected_at: NonEmptyString
    encryption: SmbStatusEncrypt
    signing: SmbStatusSign
    num_channels: int


class SmbOpenFile(BaseModel):
    server_id: SmbServerId
    username: NonEmptyString
    uid: int
    share_file_id: NonEmptyString
    sharemode: SmbOpenFileShareMode
    access_mask: SmbOpenFileAccessMask
    caching: SmbOpenFileCaching
    oplock: SmbOpenFileOplock
    lease: SmbOpenFileLease
    opened_at: NonEmptyString


class LocksEntry(BaseModel):
    service_path: NonEmptyString
    filename: NonEmptyString
    fileid: SmbOpenFileId
    num_pending_deletes: int
    opens: dict[str, SmbOpenFile]


class SessionsEntry(BaseModel):
    session_id: NonEmptyString
    server_id: SmbServerId
    uid: int
    gid: int
    username: NonEmptyString
    groupname: NonEmptyString
    creation_time: NonEmptyString
    expiration_time: NonEmptyString
    auth_time: NonEmptyString
    remote_machine: NonEmptyString
    hostname: NonEmptyString
    session_dialect: NonEmptyString
    client_guid: NonEmptyString
    encryption: SmbStatusEncrypt
    signing: SmbStatusSign
    channels: dict[str, SmbServerChannel]


class AllEntry(SessionsEntry):
    share_connections: list[ShareEntry]


class NotificationsEntry(BaseModel):
    server_id: SmbServerId
    path: NonEmptyString
    notification_filter: NonEmptyString = Field(alias='filter')
    subdir_filter: NonEmptyString
    creation_time: NonEmptyString


class SmbStatusOptions(BaseModel):
    verbose: bool = True
    fast: bool = False
    restrict_user: str = EMPTY_STRING
    restrict_session: str = EMPTY_STRING
    resolve_uids: bool = True


class SmbStatusArgs(BaseModel):
    info_level: SmbStatusInformationType = 'SESSIONS'
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default=QueryOptions())
    status_options: SmbStatusOptions = SmbStatusOptions()


class SmbStatusResult(BaseModel):
    result: query_result(ShareEntry) | query_result(LocksEntry) | query_result(SessionsEntry) | query_result(NotificationsEntry)
