from middlewared.schema import (
    Bool,
    Dict,
    Int,
    IPAddr,
    Str,
    UUID,
)
from .common import (
    AuditEnum,
    AuditEventParam,
    AuditSchema,
    AUDIT_VERS,
    audit_schema_from_base,
    convert_schema_to_set,
)


class AuditSudoEventType(AuditEnum):
    ACCEPT = 'ACCEPT'
    REJECT = 'REJECT'


AUDIT_EVENT_DATA_SUDO_ACCEPT = Dict(
    str(AuditEventParam.EVENT_DATA),
    AUDIT_VERS,
)


AUDIT_EVENT_DATA_SUDO_REJECT = Dict(
    str(AuditEventParam.EVENT_DATA),
    AUDIT_VERS,
)


AUDIT_EVENT_SUDO_SCHEMAS = []


AUDIT_EVENT_SUDO_BASE_SCHEMA = AuditSchema(
    'audit_entry_sudo',
    UUID(AuditEventParam.AUDIT_ID.value),
    Int(AuditEventParam.MESSAGE_TIMESTAMP.value),
    Dict(AuditEventParam.TIMESTAMP.value),
    IPAddr(AuditEventParam.ADDRESS.value),
    Str(AuditEventParam.USERNAME.value),
    UUID(AuditEventParam.SESSION.value),
    Str(AuditEventParam.SERVICE.value, enum=['SUDO']),
    Bool('success'),
)


AUDIT_EVENT_SUDO_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SUDO_BASE_SCHEMA,
    'audit_entry_sudo_accept',
    Str(AuditEventParam.EVENT.value, enum=[AuditSudoEventType.ACCEPT.name]),
    AUDIT_EVENT_DATA_SUDO_ACCEPT,
))


AUDIT_EVENT_SUDO_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_SUDO_BASE_SCHEMA,
    'audit_entry_sudo_reject',
    Str(AuditEventParam.EVENT.value, enum=[AuditSudoEventType.REJECT.name]),
    AUDIT_EVENT_DATA_SUDO_REJECT,
))


AUDIT_EVENT_SUDO_JSON_SCHEMAS = [
    schema.to_json_schema() for schema in AUDIT_EVENT_SUDO_SCHEMAS
]


AUDIT_EVENT_SUDO_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_SUDO_JSON_SCHEMAS)
