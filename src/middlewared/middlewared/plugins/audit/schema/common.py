import enum

from copy import deepcopy
from middlewared.schema import (
    Dict,
    Int,
    List,
    Str,
)


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


class AuditFileHandleType(AuditEnum):
    DEV_INO = 'DEV_INO'
    UUID = 'UUID'


class AuditResultType(AuditEnum):
    UNIX = 'UNIX'
    NTSTATUS = 'NTSTATUS'


class AuditFileType(AuditEnum):
    BLOCK = 'BLOCK'
    CHARACTER = 'CHARACTER'
    FIFO = 'FIFO'
    REGULAR = 'REGULAR'
    DIRECTORY = 'DIRECTORY'
    SYMLINK = 'SYMLINK'


AUDIT_VERS = Dict(
    'vers',
    Int('major', required=True),
    Int('minor', required=True)
)


AUDIT_RESULT_NTSTATUS = Dict(
    'result',
    Str('type', enum=[AuditResultType.NTSTATUS.name]),
    Int('value_raw'),
    Str('value_parsed')
)


AUDIT_RESULT_UNIX = Dict(
    'result',
    Str('type', enum=[AuditResultType.UNIX.name]),
    Int('value_raw'),
    Str('value_parsed')
)


AUDIT_FILE_HANDLE = Dict(
    'handle',
    Str('type', enum=[x.name for x in AuditFileHandleType]),
    Str('value')
)


AUDIT_FILE = Dict(
    'file',
    Str('type', enum=[x.name for x in AuditFileType]),
    Str('name'),
    Str('stream'),
    Str('path'),
    Str('snap')
)


AUDIT_UNIX_TOKEN = Dict(
    'unix_token',
    Int('uid'),
    Int('gid'),
    List('groups', items=[Int('group_id')]),
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

        if val['type'] == 'object':
            for subkey, subval in val['properties'].items():
                add_to_set(subkey, subval, current_name)

    schema_set = set()
    for entry in schema_list:
        for key, val in entry['properties'].items():
            add_to_set(key, val, '')

    return schema_set
