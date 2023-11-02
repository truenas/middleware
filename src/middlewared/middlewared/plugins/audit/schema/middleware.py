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


class AuditMiddlewareEventType(AuditEnum):
    AUTHENTICATION = 'AUTHENTICATION'
    METHOD_CALL = 'METHOD_CALL'


AUDIT_EVENT_DATA_MIDDLEWARE_AUTHENTICATION = Dict(
    str(AuditEventParam.EVENT_DATA),
    Dict('credentials',
         Str('type'),
         Dict('data', additional_attrs=True),
         null=True),
    Str('error', null=True),
    AUDIT_VERS,
)


AUDIT_EVENT_DATA_MIDDLEWARE_METHOD_CALL = Dict(
    str(AuditEventParam.EVENT_DATA),
    Str('method'),
    Str('description', null=True),
    Bool('authenticated'),
    Bool('authorized'),
    AUDIT_VERS,
)


AUDIT_EVENT_MIDDLEWARE_SCHEMAS = []


AUDIT_EVENT_MIDDLEWARE_BASE_SCHEMA = AuditSchema(
    'audit_entry_middleware',
    UUID(AuditEventParam.AUDIT_ID.value),
    Int(AuditEventParam.MESSAGE_TIMESTAMP.value),
    Dict(AuditEventParam.TIMESTAMP.value),
    IPAddr(AuditEventParam.ADDRESS.value),
    Str(AuditEventParam.USERNAME.value),
    UUID(AuditEventParam.SESSION.value),
    Str(AuditEventParam.SERVICE.value, enum=['MIDDLEWARE']),
    Dict(
        AuditEventParam.SERVICE_DATA.value,
        AUDIT_VERS,
        Str('origin', null=True),
        Dict('credentials', null=True, additional_attrs=True),
    ),
    Bool('success'),
)


AUDIT_EVENT_MIDDLEWARE_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_MIDDLEWARE_BASE_SCHEMA,
    'audit_entry_middleware_authentication',
    Str(AuditEventParam.EVENT.value, enum=[AuditMiddlewareEventType.AUTHENTICATION.name]),
    AUDIT_EVENT_DATA_MIDDLEWARE_AUTHENTICATION,
))


AUDIT_EVENT_MIDDLEWARE_SCHEMAS.append(audit_schema_from_base(
    AUDIT_EVENT_MIDDLEWARE_BASE_SCHEMA,
    'audit_entry_middleware_method_call',
    Str(AuditEventParam.EVENT.value, enum=[AuditMiddlewareEventType.METHOD_CALL.name]),
    AUDIT_EVENT_DATA_MIDDLEWARE_METHOD_CALL,
))


AUDIT_EVENT_MIDDLEWARE_JSON_SCHEMAS = [
    schema.to_json_schema() for schema in AUDIT_EVENT_MIDDLEWARE_SCHEMAS
]


AUDIT_EVENT_MIDDLEWARE_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_MIDDLEWARE_JSON_SCHEMAS)
