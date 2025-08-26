from copy import deepcopy
import enum
from typing import Iterable

from middlewared.api.base import BaseModel
from middlewared.schema import Dict, Int


class AuditEnum(enum.Enum):
    def __str__(self):
        return str(self.value)


class AuditSchema(Dict):
    def extend(self, *attrs, **kwargs):
        for i in attrs:
            self.attrs[i.name] = i

        for k, v in self.conditional_defaults.items():
            if k not in self.attrs:
                raise ValueError(f'Specified attribute {k!r} not found.')
            for k_v in ('filters', 'attrs'):
                if k_v not in v:
                    raise ValueError(f'Conditional defaults must have {k_v} specified.')
            for attr in v['attrs']:
                if attr not in self.attrs:
                    raise ValueError(f'Specified attribute {attr} not found.')

        if self.strict:
            for attr in self.attrs.values():
                if attr.required:
                    if attr.has_default:
                        raise ValueError(
                            f'Attribute {attr.name} is required and has default value at the same time, '
                            'this is forbidden in strict mode'
                        )
                else:
                    if not attr.has_default:
                        raise ValueError(
                            f'Attribute {attr.name} is not required and does not have default value, '
                            'this is forbidden in strict mode'
                        )


class AuditEventParam(AuditEnum):
    AUDIT_ID = 'audit_id'
    TIMESTAMP = 'timestamp'
    MESSAGE_TIMESTAMP = 'message_timestamp'
    ADDRESS = 'address'
    USERNAME = 'username'
    SESSION = 'session'
    SERVICE = 'service'
    SERVICE_DATA = 'service_data'
    EVENT = 'event'
    EVENT_DATA = 'event_data'
    SUCCESS = 'success'


AUDIT_VERS = Dict(
    'vers',
    Int('major', required=True),
    Int('minor', required=True)
)


class AuditEventVersion(BaseModel):
    major: int
    minor: int


def audit_schema_from_base(schema, new_name, *args):
    new_schema = deepcopy(schema)
    new_schema.extend(*args)
    new_schema.name = new_name
    return new_schema



def convert_schema_to_set(schema_list: Iterable[dict]) -> set[str]:
    """Generate a set of all dot-notated field names contained in the JSON schema."""

    def add_to_set(val: dict, current_name: str, skip_title: bool = False):
        if not skip_title:
            if current_name:
                current_name += '.'

            current_name += val['title']
            schema_set.add(current_name)

        if any_of := val.get('anyOf'):
            for subval in any_of:
                # The titles of objects contained in "anyOf" are model names. Don't use those.
                add_to_set(subval, current_name, skip_title=True)
        elif val['type'] == 'object':
            for subval in val.get('properties', {}).values():  # Fields with type `dict` do not have properties.
                add_to_set(subval, current_name)

    schema_set = set()
    for entry in schema_list:
        for val in entry['properties'].values():
            add_to_set(val, '')

    return schema_set
