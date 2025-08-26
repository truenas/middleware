from typing import Literal

from middlewared.api.base import BaseModel, IPvAnyAddress, UUID
from middlewared.api.base.jsonschema import add_attrs, replace_refs
from .common import AuditEventVersion, convert_schema_to_set


class AuditEventSMBServiceData(BaseModel):
    vers: AuditEventVersion
    service: str
    session_id: str
    tcon_id: str


class AuditEventSMB(BaseModel):
    event: str
    event_data: BaseModel
    audit_id: UUID
    message_timestamp: int
    timestamp: dict
    address: IPvAnyAddress
    username: str
    session: UUID
    service: Literal['SMB']
    service_data: AuditEventSMBServiceData
    success: bool


class AuditEventSMBResult(BaseModel):
    type: Literal['NTSTATUS', 'UNIX']
    value_raw: int
    value_parsed: str


class AuditEventSMBResultNTStatus(AuditEventSMBResult):
    type: Literal['NTSTATUS']


class AuditEventSMBResultUnix(AuditEventSMBResult):
    type: Literal['UNIX']


class AuditEventSMBUnixToken(BaseModel):
    uid: int
    gid: int
    groups: list[int]


class AuditEventSMBRenameDstFile(BaseModel):
    path: str
    stream: str
    snap: str


class AuditEventSMBRenameSrcFile(AuditEventSMBRenameDstFile):
    file_type: Literal['BLOCK', 'CHARACTER', 'FIFO', 'REGULAR', 'DIRECTORY', 'SYMLINK']


class AuditEventSMBFile(AuditEventSMBRenameDstFile):
    type: Literal['BLOCK', 'CHARACTER', 'FIFO', 'REGULAR', 'DIRECTORY', 'SYMLINK']
    name: str


class AuditEventDataSMBFileHandle(BaseModel):
    type: Literal['DEV_INO', 'UUID']
    value: str


class AuditEventSMBFileHandleOuter(BaseModel):
    handle: AuditEventDataSMBFileHandle


class AuditEventSMBAuthenticationEventData(BaseModel):
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
    result: AuditEventSMBResultNTStatus
    vers: AuditEventVersion


class AuditEventSMBAuthentication(AuditEventSMB):
    event: Literal['AUTHENTICATION']
    event_data: AuditEventSMBAuthenticationEventData


class AuditEventSMBConnectEventData(BaseModel):
    host: str
    unix_token: AuditEventSMBUnixToken
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBConnect(AuditEventSMB):
    event: Literal['CONNECT']
    event_data: AuditEventSMBConnectEventData


class AuditEventSMBDisconnectOperations(BaseModel):
    create: str
    close: str
    read: str
    write: str


class AuditEventSMBDisconnectEventData(BaseModel):
    host: str
    unix_token: AuditEventSMBUnixToken
    operations: AuditEventSMBDisconnectOperations
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBDisconnect(AuditEventSMB):
    event: Literal['DISCONNECT']
    event_data: AuditEventSMBDisconnectEventData


class AuditEventSMBCreateParameters(BaseModel):
    DesiredAccess: str
    FileAttributes: str
    ShareAccess: str
    CreateDisposition: Literal['SUPERSEDE', 'OVERWRITE_IF', 'OPEN', 'CREATE', 'OPEN_IF', 'UNKNOWN']
    CreateOptions: str


class AuditEventSMBCreateEventData(BaseModel):
    parameters: AuditEventSMBCreateParameters
    file_type: Literal['BLOCK', 'CHARACTER', 'FIFO', 'REGULAR', 'DIRECTORY', 'SYMLINK']
    file: AuditEventSMBFile
    result: AuditEventSMBResultNTStatus
    vers: AuditEventVersion


class AuditEventSMBCreate(AuditEventSMB):
    event: Literal['CREATE']
    event_data: AuditEventSMBCreateEventData


class AuditEventSMBCloseOperations(BaseModel):
    read_cnt: str
    read_bytes: str
    write_cnt: str
    write_bytes: str


class AuditEventSMBCloseEventData(BaseModel):
    file: AuditEventSMBFileHandleOuter
    operations: AuditEventSMBCloseOperations
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBClose(AuditEventSMB):
    event: Literal['CLOSE']
    event_data: AuditEventSMBCloseEventData


class AuditEventSMBSetAttrEventData(BaseModel):
    attr_type: Literal['DOSMODE', 'TIMESTAMP']
    dosmode: str
    ts: dict
    file: AuditEventSMBFileHandleOuter
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBSetAttr(AuditEventSMB):
    event: Literal['SET_ATTR']
    event_data: AuditEventSMBSetAttrEventData


class AuditEventSMBRenameEventData(BaseModel):
    src_file: AuditEventSMBRenameSrcFile
    dst_file: AuditEventSMBRenameDstFile
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBRename(AuditEventSMB):
    event: Literal['RENAME']
    event_data: AuditEventSMBRenameEventData


class AuditEventSMBUnlinkEventData(BaseModel):
    file: AuditEventSMBFile
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBUnlink(AuditEventSMB):
    event: Literal['UNLINK']
    event_data: AuditEventSMBUnlinkEventData


class AuditEventSMBReadEventData(BaseModel):
    file: AuditEventSMBFileHandleOuter
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBRead(AuditEventSMB):
    event: Literal['READ']
    event_data: AuditEventSMBReadEventData


class AuditEventSMBWriteEventData(BaseModel):
    file: AuditEventSMBFileHandleOuter
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBWrite(AuditEventSMB):
    event: Literal['WRITE']
    event_data: AuditEventSMBWriteEventData


class AuditEventSMBOffloadReadEventData(BaseModel):
    file: AuditEventSMBFileHandleOuter
    result: AuditEventSMBResultNTStatus
    vers: AuditEventVersion


class AuditEventSMBOffloadRead(AuditEventSMB):
    event: Literal['OFFLOAD_READ']
    event_data: AuditEventSMBOffloadReadEventData


class AuditEventSMBOffloadWriteEventData(BaseModel):
    file: AuditEventSMBFileHandleOuter
    result: AuditEventSMBResultNTStatus
    vers: AuditEventVersion


class AuditEventSMBOffloadWrite(AuditEventSMB):
    event: Literal['OFFLOAD_WRITE']
    event_data: AuditEventSMBOffloadWriteEventData


class AuditEventSMBSetACLEventData(BaseModel):
    file: AuditEventSMBFile
    secinfo: str
    sd: str
    result: AuditEventSMBResultNTStatus
    vers: AuditEventVersion


class AuditEventSMBSetACL(AuditEventSMB):
    event: Literal['SET_ACL']
    event_data: AuditEventSMBSetACLEventData


class AuditEventSMBFSCTLFunction(BaseModel):
    raw: str
    parsed: str


class AuditEventSMBFSCTLEventData(BaseModel):
    function: AuditEventSMBFSCTLFunction
    file: AuditEventSMBFileHandleOuter
    result: AuditEventSMBResultNTStatus
    vers: AuditEventVersion


class AuditEventSMBFSCTL(AuditEventSMB):
    event: Literal['FSCTL']
    event_data: AuditEventSMBFSCTLEventData


class AuditEventSMBSetQuotaQt(BaseModel):
    type: Literal['USER', 'GROUP']
    bsize: str
    soflimit: str
    hardlimit: str
    isoftlimit: str
    ihardlimit: str


class AuditEventSMBSetQuotaEventData(BaseModel):
    qt: AuditEventSMBSetQuotaQt
    result: AuditEventSMBResultUnix
    vers: AuditEventVersion


class AuditEventSMBSetQuota(AuditEventSMB):
    event: Literal['SET_QUOTA']
    event_data: AuditEventSMBSetQuotaEventData


# Below are schema classes for the full SMB audit events that are written to the
# auditing database and returned in `audit.query` requests. We start with a generic
# base instance and then extend a copy of the generalized event with event-specific
# `event_data` defined above.


AUDIT_EVENT_SMB_JSON_SCHEMAS = [
    add_attrs(replace_refs(event_model.model_json_schema()))
    for event_model in (
        AuditEventSMBAuthentication,
        AuditEventSMBConnect,
        AuditEventSMBDisconnect,
        AuditEventSMBCreate,
        AuditEventSMBClose,
        AuditEventSMBSetAttr,
        AuditEventSMBRename,
        AuditEventSMBUnlink,
        AuditEventSMBRead,
        AuditEventSMBWrite,
        AuditEventSMBOffloadRead,
        AuditEventSMBOffloadWrite,
        AuditEventSMBSetACL,
        AuditEventSMBFSCTL,
        AuditEventSMBSetQuota,
    )
]


AUDIT_EVENT_SMB_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_SMB_JSON_SCHEMAS)
