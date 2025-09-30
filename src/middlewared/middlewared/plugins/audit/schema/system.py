from typing import Literal

from middlewared.api.base import BaseModel
from middlewared.api.base.jsonschema import add_attrs, replace_refs
from .common import AuditEvent, convert_schema_to_set


class AuditEventSystemEventDataSyscall(BaseModel):
    tty: str | None
    SYSCALL: str
    auid: int
    AUID: str
    uid: int
    UID: str
    gid: int
    GID: str


class AuditEventSystemLoginEventData(BaseModel):
    proctitle: str
    syscall: AuditEventSystemEventDataSyscall


class AuditEventSystemPrivilegedEventData(BaseModel):
    proctitle: str
    syscall: AuditEventSystemEventDataSyscall
    cwd: str


class AuditEventSystemEscalationEventData(AuditEventSystemPrivilegedEventData):
    # Same as Privileged Event (for now)
    pass


class AuditEventSystem(AuditEvent):
    event: Literal['LOGIN', 'PRIVILEGED', 'ESCALATION']
    event_data: (
        AuditEventSystemLoginEventData |
        AuditEventSystemPrivilegedEventData |
        AuditEventSystemEscalationEventData
    )
    service: Literal['SYSTEM']


class AuditEventSystemLogin(AuditEventSystem):
    event: Literal['LOGIN']
    event_data: AuditEventSystemLoginEventData


class AuditEventSystemPrivileged(AuditEventSystem):
    event: Literal['PRIVILEGED']
    event_data: AuditEventSystemPrivilegedEventData


class AuditEventSystemEscalation(AuditEventSystem):
    event: Literal['ESCALATION']
    event_data: AuditEventSystemEscalationEventData


AUDIT_EVENT_SYSTEM_JSON_SCHEMAS = [
    add_attrs(replace_refs(event_model.model_json_schema()))
    for event_model in (
        AuditEventSystemLogin,
        AuditEventSystemPrivileged,
        AuditEventSystemEscalation,
    )
]


AUDIT_EVENT_SYSTEM_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_SYSTEM_JSON_SCHEMAS)
