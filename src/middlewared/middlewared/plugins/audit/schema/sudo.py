from typing import Literal

from middlewared.api.base import BaseModel
from middlewared.api.base.jsonschema import add_attrs, replace_refs
from .common import AuditEvent, AuditEventVersion, convert_schema_to_set


class AuditEventSudoEventData(BaseModel):
    vers: AuditEventVersion


class AuditEventSudo(AuditEvent):
    event: Literal['ACCEPT', 'REJECT']
    event_data: AuditEventSudoEventData
    service: Literal['SUDO']


class AuditEventSudoAccept(AuditEventSudo):
    event: Literal['ACCEPT']


class AuditEventSudoReject(AuditEventSudo):
    event: Literal['REJECT']


AUDIT_EVENT_SUDO_JSON_SCHEMAS = [
    add_attrs(replace_refs(model.model_json_schema()))
    for model in (
        AuditEventSudoAccept,
        AuditEventSudoReject,
    )
]


AUDIT_EVENT_SUDO_PARAM_SET = convert_schema_to_set(AUDIT_EVENT_SUDO_JSON_SCHEMAS)
