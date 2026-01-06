from typing import Literal

from middlewared.api.base import BaseModel
from middlewared.api.base.jsonschema import add_attrs, replace_refs
from .common import AuditEvent, AuditEventVersion, convert_schema_to_set


class AuditEventMiddlewareAuthenticationEventDataCredentials(BaseModel):
    type: str
    data: dict


class AuditEventMiddlewareAuthenticationEventData(BaseModel):
    credentials: AuditEventMiddlewareAuthenticationEventDataCredentials | None
    error: str | None
    vers: AuditEventVersion


class AuditEventMiddlewareMethodCallEventData(BaseModel):
    method: str
    params: list
    description: str | None
    authenticated: bool
    authorized: bool
    vers: AuditEventVersion


class AuditEventMiddlewareRebootShutdownEventData(BaseModel):
    reason: str | None


class AuditEventMiddlewareServiceData(BaseModel):
    vers: AuditEventVersion
    origin: str | None
    protocol: Literal['REST', 'WEBSOCKET']
    credentials: dict | None


class AuditEventMiddleware(AuditEvent):
    event: Literal['AUTHENTICATION', 'METHOD_CALL', 'REBOOT', 'SHUTDOWN']
    event_data: (
        AuditEventMiddlewareAuthenticationEventData |
        AuditEventMiddlewareMethodCallEventData |
        AuditEventMiddlewareRebootShutdownEventData
    )
    service: Literal['MIDDLEWARE']
    service_data: AuditEventMiddlewareServiceData


class AuditEventMiddlewareAuthentication(AuditEventMiddleware):
    event: Literal['AUTHENTICATION']
    event_data: AuditEventMiddlewareAuthenticationEventData


class AuditEventMiddlewareMethodCall(AuditEventMiddleware):
    event: Literal['METHOD_CALL']
    event_data: AuditEventMiddlewareMethodCallEventData


class AuditEventMiddlewareRebootShutdownCall(AuditEventMiddleware):
    event: Literal['REBOOT', 'SHUTDOWN']
    event_data: AuditEventMiddlewareRebootShutdownEventData


AUDIT_EVENT_MIDDLEWARE_JSON_SCHEMAS = [
    add_attrs(replace_refs(event_model.model_json_schema()))
    for event_model in (
        AuditEventMiddlewareAuthentication,
        AuditEventMiddlewareMethodCall,
        AuditEventMiddlewareRebootShutdownCall,
    )
]


AUDIT_EVENT_MIDDLEWARE_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_MIDDLEWARE_JSON_SCHEMAS)
