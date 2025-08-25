from typing import Literal

from middlewared.api.base import BaseModel, IPvAnyAddress, UUID
from .common import convert_schema_to_set


class AuditVersion(BaseModel):
    major: int
    minor: int


class AuditEventSMBServiceData(BaseModel):
    vers: AuditVersion
    service: str
    session_id: str
    tcon_id: str


class AuditEventSMB(BaseModel):
    audit_id: UUID
    message_timestamp: int
    timestamp: dict
    address: IPvAnyAddress
    username: str
    session: UUID
    service: Literal['SMB']
    service_data: AuditEventSMBServiceData
    success: bool


class AuditResult(BaseModel):
    type: Literal['NTSTATUS', 'UNIX']
    value_raw: int
    value_parsed: str


class AuditResultNTStatus(AuditResult):
    type: Literal['NTSTATUS']


class AuditUnixToken(BaseModel):
    uid: int
    gid: int
    groups: list[int]


class AuditResultUnix(AuditResult):
    type: Literal['UNIX']


class AuditEventDataSMBRenameDstFile(BaseModel):
    path: str
    stream: str
    snap: str


class AuditEventDataSMBRenameSrcFile(AuditEventDataSMBRenameDstFile):
    file_type: Literal['BLOCK', 'CHARACTER', 'FIFO', 'REGULAR', 'DIRECTORY', 'SYMLINK']


class AuditFile(AuditEventDataSMBRenameDstFile):
    type: Literal['BLOCK', 'CHARACTER', 'FIFO', 'REGULAR', 'DIRECTORY', 'SYMLINK']
    name: str


class AuditFileHandle(BaseModel):
    type: Literal['DEV_INO', 'UUID']
    value: str


class AuditFileHandleOuter(BaseModel):
    handle: AuditFileHandle


# Below are schema class instances for `event_data` for SMB audit events.


class AuditEventDataSMBAuthentication(AuditEventSMB):
    event: Literal['AUTHENTICATION']
    logonId: str
    logonType: int
    localAddress: str
    remoteAddress: str
    serviceDescription: str
    authDescription: str
    clientDomain: str
    clientAccount: str
    workstation: str
    becameAccount: str
    becameDomain: str
    becameSid: str
    mappedAccount: str
    mappedDomain: str
    netlogonComputer: str
    netlogonTrustAccount: str
    netlogonNegotiateFlags: str
    netlogonSecureChannelType: str
    netlogonTrustAccountSid: str
    passwordType: str
    result: AuditResultNTStatus
    vers: AuditVersion


class AuditEventDataSMBConnect(AuditEventSMB):
    event: Literal['CONNECT']
    host: str
    unix_token: AuditUnixToken
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBDisconnectOperations(BaseModel):
    create: str
    close: str
    read: str
    write: str


class AuditEventDataSMBDisconnect(AuditEventSMB):
    event: Literal['DISCONNECT']
    host: str
    unix_token: AuditUnixToken
    operations: AuditEventDataSMBDisconnectOperations
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBCreateParameters(BaseModel):
    DesiredAccess: str
    FileAttributes: str
    ShareAccess: str
    CreateDisposition: Literal['SUPERSEDE', 'OVERWRITE_IF', 'OPEN', 'CREATE', 'OPEN_IF', 'UNKNOWN']
    CreateOptions: str


class AuditEventDataSMBCreate(AuditEventSMB):
    event: Literal['CREATE']
    parameters: AuditEventDataSMBCreateParameters
    file_type: Literal['BLOCK', 'CHARACTER', 'FIFO', 'REGULAR', 'DIRECTORY', 'SYMLINK']
    file: AuditFile
    result: AuditResultNTStatus
    vers: AuditVersion


class AuditEventDataSMBCloseOperations(BaseModel):
    read_cnt: str
    read_bytes: str
    write_cnt: str
    write_bytes: str


class AuditEventDataSMBClose(AuditEventSMB):
    event: Literal['CLOSE']
    file: AuditFileHandleOuter
    operations: AuditEventDataSMBCloseOperations
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBSetAttr(AuditEventSMB):
    event: Literal['SET_ATTR']
    attr_type: Literal['DOSMODE', 'TIMESTAMP']
    dosmode: str
    ts: dict
    file: AuditFileHandleOuter
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBRename(AuditEventSMB):
    event: Literal['RENAME']
    src_file: AuditEventDataSMBRenameSrcFile
    dst_file: AuditEventDataSMBRenameDstFile
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBUnlink(AuditEventSMB):
    event: Literal['UNLINK']
    file: AuditFile
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBRead(AuditEventSMB):
    event: Literal['READ']
    file: AuditFileHandleOuter
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBWrite(AuditEventSMB):
    event: Literal['WRITE']
    file: AuditFileHandleOuter
    result: AuditResultUnix
    vers: AuditVersion


class AuditEventDataSMBOffloadRead(AuditEventSMB):
    event: Literal['OFFLOAD_READ']
    file: AuditFileHandleOuter
    result: AuditResultNTStatus
    vers: AuditVersion


class AuditEventDataSMBOffloadWrite(AuditEventSMB):
    event: Literal['OFFLOAD_WRITE']
    file: AuditFileHandleOuter
    result: AuditResultNTStatus
    vers: AuditVersion


class AuditEventDataSMBSetACL(AuditEventSMB):
    event: Literal['SET_ACL']
    file: AuditFile
    secinfo: str
    sd: str
    result: AuditResultNTStatus
    vers: AuditVersion


class AuditEventDataSMBFSCTLFunction(BaseModel):
    raw: str
    parsed: str


class AuditEventDataSMBFSCTL(AuditEventSMB):
    event: Literal['FSCTL']
    function: AuditEventDataSMBFSCTLFunction
    file: AuditFileHandleOuter
    result: AuditResultNTStatus
    vers: AuditVersion


class AuditEventDataSMBSetQuotaQt(BaseModel):
    type: Literal['USER', 'GROUP']
    bsize: str
    soflimit: str
    hardlimit: str
    isoftlimit: str
    ihardlimit: str


class AuditEventDataSMBSetQuota(AuditEventSMB):
    event: Literal['SET_QUOTA']
    qt: AuditEventDataSMBSetQuotaQt
    result: AuditResultUnix
    vers: AuditVersion


# Below are schema classes for the full SMB audit events that are written to the
# auditing database and returned in `audit.query` requests. We start with a generic
# base instance and then extend a copy of the generalized event with event-specific
# `event_data` defined above.


AUDIT_EVENT_SMB_JSON_SCHEMAS = [
    event_model.model_json_schema()
    for event_model in (
        AuditEventDataSMBAuthentication,
        AuditEventDataSMBConnect,
        AuditEventDataSMBDisconnect,
        AuditEventDataSMBCreate,
        AuditEventDataSMBClose,
        AuditEventDataSMBSetAttr,
        AuditEventDataSMBRename,
        AuditEventDataSMBUnlink,
        AuditEventDataSMBRead,
        AuditEventDataSMBWrite,
        AuditEventDataSMBOffloadRead,
        AuditEventDataSMBOffloadWrite,
        AuditEventDataSMBSetACL,
        AuditEventDataSMBFSCTL,
        AuditEventDataSMBSetQuota,
    )
]


AUDIT_EVENT_SMB_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_SMB_JSON_SCHEMAS)
