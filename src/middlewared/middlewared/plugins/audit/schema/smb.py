from .common import (
    AuditEnum,
    AuditEventParam,
    AuditSchema,
    AUDIT_VERS,
    AUDIT_RESULT_NTSTATUS,
    AUDIT_RESULT_UNIX,
    AuditFileType,
    AUDIT_FILE,
    AUDIT_FILE_HANDLE,
    audit_schema_from_base,
    AUDIT_UNIX_TOKEN,
    convert_schema_to_set
)
from middlewared.schema import (
    Bool,
    Dict,
    Int,
    IPAddr,
    Str,
    UUID
)


class AuditSmbCreateDisp(AuditEnum):
    """
    This enum contains all possible values of the SMB2 CREATE CreateDisposition.
    """
    SUPERSEDE = 'SUPERSEDE'
    OVERWRITE_IF = 'OVERWRITE_IF'
    OPEN = 'OPEN'
    CREATE = 'CREATE'
    OPEN_IF = 'OPEN_IF'
    UNKNOWN = 'UNKNOWN'


class AuditSmbEventType(AuditEnum):
    """
    This enum contains all possible SMB audit events. Values correspond with
    `event` written to auditing SQLite database.
    """
    AUTHENTICATION = 'AUTHENTICATION'
    CONNECT = 'CONNECT'
    DISCONNECT = 'DISCONNECT'
    CREATE = 'CREATE'
    CLOSE = 'CLOSE'
    READ = 'READ'
    WRITE = 'WRITE'
    OFFLOAD_READ = 'OFFLOAD_READ'
    OFFLOAD_WRITE = 'OFFLOAD_WRITE'
    RENAME = 'RENAME'
    UNLINK = 'UNLINK'
    SET_ACL = 'SET_ACL'
    SET_ATTR = 'SET_ATTR'
    SET_QUOTA = 'SET_QUOTA'
    FSCTL = 'FSCTL'


class AuditSetattrType(AuditEnum):
    DOSMODE = 'DOSMODE'
    TIMESTAMP = 'TIMESTAMP'


"""
Below are schema class instances for `event_data` for SMB audit events.
"""


AUDIT_EVENT_DATA_SMB_AUTHENTICATION = Dict(
    str(AuditEventParam.EVENT_DATA),
    Str('logonId'),
    Int('logonType'),
    Str('localAddress'),
    Str('remoteAddress'),
    Str('serviceDescription'),
    Str('authDescription'),
    Str('clientDomain'),
    Str('clientAccount'),
    Str('workstation'),
    Str('becameAccount'),
    Str('becameDomain'),
    Str('becameSid'),
    Str('mappedAccount'),
    Str('mappedDomain'),
    Str('netlogonComputer'),
    Str('netlogonTrustAccount'),
    Str('netlogonNegotiateFlags'),
    Str('netlogonSecureChannelType'),
    Str('netlogonTrustAccountSid'),
    Str('passwordType'),
    AUDIT_RESULT_NTSTATUS,
    AUDIT_VERS,
)


AUDIT_EVENT_DATA_SMB_CONNECT = Dict(
    str(AuditEventParam.EVENT_DATA),
    Str('host'),
    AUDIT_UNIX_TOKEN,
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_DISCONNECT = Dict(
    str(AuditEventParam.EVENT_DATA),
    Str('host'),
    AUDIT_UNIX_TOKEN,
    Dict(
        'operations',
        Str('create'),
        Str('close'),
        Str('read'),
        Str('write')
    ),
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_CREATE = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict(
        'parameters',
        Str('DesiredAccess'),
        Str('FileAttributes'),
        Str('ShareAccess'),
        Str('CreateDisposition', enum=[x.name for x in AuditSmbCreateDisp]),
        Str('CreateOptions')
    ),
    Str('file_type', enum=[x.name for x in AuditFileType]),
    AUDIT_FILE,
    AUDIT_RESULT_NTSTATUS,
    AUDIT_VERS,
)


AUDIT_EVENT_DATA_SMB_CLOSE = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict('file', AUDIT_FILE_HANDLE),
    Dict(
        'operations',
        Str('read_cnt'),
        Str('read_bytes'),
        Str('write_cnt'),
        Str('write_bytes')
    ),
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_SET_ATTR = Dict(
    str(AuditEventParam.EVENT_DATA),
    Str('attr_type', enum=[x.name for x in AuditSetattrType]),
    Str('dosmode'),
    Dict('ts'),
    Dict('file', AUDIT_FILE_HANDLE),
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_RENAME = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict(
        'src_file',
        Str('file_type', enum=[x.name for x in AuditFileType]),
        Str('path'),
        Str('stream'),
        Str('snap')
    ),
    Dict(
        'dst_file',
        Str('path'),
        Str('stream'),
        Str('snap'),
    ),
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_UNLINK = Dict(
    str(AuditEventParam.EVENT_DATA),
    AUDIT_FILE,
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_READ = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict('file', AUDIT_FILE_HANDLE),
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_WRITE = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict('file', AUDIT_FILE_HANDLE),
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_OFFLOAD_READ = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict('file', AUDIT_FILE_HANDLE),
    AUDIT_RESULT_NTSTATUS,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_OFFLOAD_WRITE = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict('file', AUDIT_FILE_HANDLE),
    AUDIT_RESULT_NTSTATUS,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_SET_ACL = Dict(
    str(AuditEventParam.EVENT_DATA),
    AUDIT_FILE,
    Str('secinfo'),
    Str('sd'),
    AUDIT_RESULT_NTSTATUS,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_FSCTL = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict(
        'function',
        Str('raw'),
        Str('parsed')
    ),
    Dict('file', AUDIT_FILE_HANDLE),
    AUDIT_RESULT_NTSTATUS,
    AUDIT_VERS
)


AUDIT_EVENT_DATA_SMB_SET_QUOTA = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict(
        'qt',
        Str('type', enum=['USER', 'GROUP']),
        Str('bsize'),
        Str('soflimit'),
        Str('hardlimit'),
        Str('isoftlimit'),
        Str('ihardlimit')
    ),
    AUDIT_RESULT_UNIX,
    AUDIT_VERS
)


"""
Below are schema classes for the full SMB audit events that are written to the
auditing database and returned in `audit.query` requests. We start with a generic
base instance and then extend a copy of the generalized event with event-specific
`event_data` defined above.
"""


AUDIT_EVENT_SMB_SCHEMAS = []


AUDIT_EVENT_SMB_BASE_SCHEMA = AuditSchema(
    'audit_entry_smb',
    UUID(AuditEventParam.AUDIT_ID.value),
    Int(AuditEventParam.MESSAGE_TIMESTAMP.value),
    Dict(AuditEventParam.TIMESTAMP.value),
    IPAddr(AuditEventParam.ADDRESS.value),
    Str(AuditEventParam.USERNAME.value),
    UUID(AuditEventParam.SESSION.value),
    Str(AuditEventParam.SERVICE.value, enum=['SMB']),
    Dict(
        AuditEventParam.SERVICE_DATA.value,
        AUDIT_VERS,
        Str('service'),
        Str('session_id'),
        Str('tcon_id')
    ),
    Bool('success')
)


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_authentication',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.AUTHENTICATION.name]),
    AUDIT_EVENT_DATA_SMB_AUTHENTICATION
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_connect',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.CONNECT.name]),
    AUDIT_EVENT_DATA_SMB_CONNECT
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_disconnect',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.DISCONNECT.name]),
    AUDIT_EVENT_DATA_SMB_DISCONNECT
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_create',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.CREATE.name]),
    AUDIT_EVENT_DATA_SMB_CREATE
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_close',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.CLOSE.name]),
    AUDIT_EVENT_DATA_SMB_CLOSE
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_set_attr',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.SET_ATTR.name]),
    AUDIT_EVENT_DATA_SMB_SET_ATTR
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_rename',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.RENAME.name]),
    AUDIT_EVENT_DATA_SMB_RENAME
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_unlink',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.UNLINK.name]),
    AUDIT_EVENT_DATA_SMB_UNLINK
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_read',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.READ.name]),
    AUDIT_EVENT_DATA_SMB_READ
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_write',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.WRITE.name]),
    AUDIT_EVENT_DATA_SMB_WRITE
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_offload_read',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.OFFLOAD_READ.name]),
    AUDIT_EVENT_DATA_SMB_OFFLOAD_READ
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_offload_write',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.OFFLOAD_WRITE.name]),
    AUDIT_EVENT_DATA_SMB_OFFLOAD_WRITE
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_set_acl',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.SET_ACL.name]),
    AUDIT_EVENT_DATA_SMB_SET_ACL
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_fsctl',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.FSCTL.name]),
    AUDIT_EVENT_DATA_SMB_FSCTL
))


AUDIT_EVENT_SMB_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SMB_BASE_SCHEMA,
    'audit_entry_smb_set_quota',
    Str(AuditEventParam.EVENT.value, enum=[AuditSmbEventType.SET_QUOTA.name]),
    AUDIT_EVENT_DATA_SMB_SET_QUOTA
))


AUDIT_EVENT_SMB_JSON_SCHEMAS = [
    schema.to_json_schema() for schema in AUDIT_EVENT_SMB_SCHEMAS
]


AUDIT_EVENT_SMB_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_SMB_JSON_SCHEMAS)
