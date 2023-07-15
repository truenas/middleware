from .adaptable_schemas import Bool
from .dict_schema import Dict
from .integer_schema import Int
from .string_schema import Str


def convert_schema(spec):
    t = spec.pop('type')
    name = spec.pop('name')
    if t in ('int', 'integer'):
        return Int(name, **spec)
    elif t in ('str', 'string'):
        return Str(name, **spec)
    elif t in ('bool', 'boolean'):
        return Bool(name, **spec)
    elif t == 'dict':
        return Dict(name, *spec.get('args', []), **spec.get('kwargs', {}))
    raise ValueError(f'Unknown type: {t}')
