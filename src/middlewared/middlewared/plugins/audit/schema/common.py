from copy import deepcopy
import enum

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


def audit_schema_from_base(schema, new_name, *args):
    new_schema = deepcopy(schema)
    new_schema.extend(*args)
    new_schema.name = new_name
    return new_schema



def convert_schema_to_set(schema_list):
    def add_to_set(key, val, current_name):
        if current_name:
            current_name += '.'

        current_name += val['title']
        schema_set.add(current_name)

        if val.get('type') == 'object':  # May have anyOf instead of type
            for subkey, subval in val.get('properties', {}).items():  # May not have properties if type is `dict`
                add_to_set(subkey, subval, current_name)

    schema_set = set()
    for entry in schema_list:
        for key, val in entry['properties'].items():
            add_to_set(key, val, '')

    return schema_set
