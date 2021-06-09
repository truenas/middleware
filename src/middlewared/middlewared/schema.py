import asyncio
import copy
import functools
import json
import textwrap
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
import errno
import inspect
import ipaddress
import os

from croniter import croniter

from middlewared.service_exception import ValidationErrors
from middlewared.settings import conf
from middlewared.utils import filter_list

NOT_PROVIDED = object()


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
        return Dict(name, **spec)
    raise ValueError(f'Unknown type: {t}')


class Schemas(dict):

    def add(self, schema):
        if schema.name in self:
            raise ValueError(f'Schema "{schema.name}" is already registered')
        super().__setitem__(schema.name, schema)


class Error(Exception):

    def __init__(self, attribute, errmsg, errno=errno.EINVAL):
        self.attribute = attribute
        self.errmsg = errmsg
        self.errno = errno
        self.extra = None

    def __str__(self):
        return '[{0}] {1}'.format(self.attribute, self.errmsg)


class EnumMixin(object):

    def __init__(self, *args, **kwargs):
        self.enum = kwargs.pop('enum', None)
        super(EnumMixin, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if self.enum is None:
            return value
        if value is None and self.null:
            return value
        if not isinstance(value, (list, tuple)):
            tmp = [value]
        else:
            tmp = value
        for v in tmp:
            if v not in self.enum:
                raise Error(self.name, f'Invalid choice: {value}')
        return value


class Attribute(object):

    def __init__(
        self, name='', title=None, description=None, required=False, null=False, empty=True, private=False,
        validators=None, register=False, hidden=False, editable=True, example=None, **kwargs
    ):
        self.name = name
        self.has_default = 'default' in kwargs and kwargs['default'] is not NOT_PROVIDED
        self.default = kwargs.pop('default', None)
        self.required = required
        self.null = null
        self.empty = empty
        self.private = private
        self.title = title or name
        self.description = description
        self.validators = validators or []
        self.register = register
        self.hidden = hidden
        self.editable = editable
        self.resolved = False
        if example:
            self.description = (description or '') + '\n' + textwrap.dedent(f'''
            Example(s):
            ```
            ''') + json.dumps(example, indent=4) + textwrap.dedent('''
            ```
            ''')
        # When a field is marked as non-editable, it must specify a default
        if not self.editable and not self.has_default:
            raise Error(self.name, 'Default value must be specified when attribute is marked as non-editable.')

    def clean(self, value):
        if value is None and self.null is False:
            raise Error(self.name, 'null not allowed')
        if value is NOT_PROVIDED:
            if self.has_default:
                value = copy.deepcopy(self.default)
            else:
                raise Error(self.name, 'attribute required')
        if not self.editable and value != self.default:
            raise Error(self.name, 'Field is not editable.')
        return value

    def has_private(self):
        return self.private

    def dump(self, value):
        if self.private:
            return "********"

        return value

    def validate(self, value):
        verrors = ValidationErrors()

        for validator in self.validators:
            try:
                validator(value)
            except ValueError as e:
                verrors.add(self.name, str(e))

        if verrors:
            raise verrors

    def to_json_schema(self, parent=None):
        """This method should return the json-schema v4 equivalent for the
        given attribute.
        """
        raise NotImplementedError("Attribute must implement to_json_schema method")

    def _to_json_schema_common(self, parent):
        schema = {}

        schema['_name_'] = self.name

        if self.title:
            schema['title'] = self.title

        if self.description:
            schema['description'] = self.description

        if self.has_default:
            schema['default'] = self.default

        schema['_required_'] = self.required

        return schema

    def resolve(self, schemas):
        """
        After every plugin is initialized this method is called for every method param
        so that the real attribute is evaluated.
        e.g.
        @params(
            Patch('schema-name', 'new-name', ('add', {'type': 'string', 'name': test'})),
            Ref('schema-test'),
        )
        will resolve to:
        @params(
            Dict('new-name', ...)
            Dict('schema-test', ...)
        )
        """
        self.resolved = True
        if self.register:
            schemas.add(self)
        return self

    def copy(self):
        cp = copy.deepcopy(self)
        cp.register = False
        return cp


class Any(Attribute):

    def to_json_schema(self, parent=None):
        return {
            'anyOf': [
                {'type': 'string'},
                {'type': 'integer'},
                {'type': 'boolean'},
                {'type': 'object'},
                {'type': 'array'},
            ],
            'nullable': self.null,
            **self._to_json_schema_common(parent),
        }


class Str(EnumMixin, Attribute):

    def __init__(self, *args, **kwargs):
        # Sqlite limits ( (2 ** 31) - 1 ) for storing text - https://www.sqlite.org/limits.html
        self.max_length = kwargs.pop('max_length', 1024) or (2 ** 31) - 1
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super(Str, self).clean(value)
        if value is None:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            raise Error(self.name, 'Not a string')
        if not self.empty and not value:
            raise Error(self.name, 'Empty value not allowed')
        return value

    def to_json_schema(self, parent=None):
        schema = self._to_json_schema_common(parent)

        if self.null:
            schema['type'] = ['string', 'null']
        else:
            schema['type'] = 'string'

        if self.enum is not None:
            schema['enum'] = self.enum

        return schema

    def validate(self, value):
        if value is None:
            return value

        verrors = ValidationErrors()

        if value and len(str(value)) > self.max_length:
            verrors.add(self.name, f'Value greater than {self.max_length} not allowed')

        verrors.check()

        return super().validate(value)


class Path(Str):

    def __init__(self, *args, **kwargs):
        self.forwarding_slash = kwargs.pop('forwarding_slash', True)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)

        if value is None:
            return value

        value = value.strip()

        if self.forwarding_slash:
            value = value.rstrip("/")
        else:
            value = value.strip("/")

        return os.path.normpath(value.strip())


class Dataset(Path):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('empty', False)
        kwargs.setdefault('forwarding_slash', False)
        super().__init__(*args, **kwargs)


class HostPath(Path):

    def validate_internal(self, verrors, value):
        pass

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        if value:
            if not os.path.exists(value):
                verrors.add(self.name, "This path does not exist.", errno.ENOENT)
            self.validate_internal(verrors, value)

        verrors.check()

        return super().validate(value)


class Dir(HostPath):

    def validate_internal(self, verrors, value):
        if not os.path.isdir(value):
            verrors.add(self.name, "This path is not a directory.", errno.ENOTDIR)


class File(HostPath):

    def validate_internal(self, verrors, value):
        if not os.path.isfile(value):
            verrors.add(self.name, "This path is not a file.", errno.EISDIR)


class IPAddr(Str):

    def __init__(self, *args, **kwargs):
        self.cidr = kwargs.pop('cidr', False)
        self.network = kwargs.pop('network', False)
        self.network_strict = kwargs.pop('network_strict', False)

        self.v4 = kwargs.pop('v4', True)
        self.v6 = kwargs.pop('v6', True)

        if self.v4 and self.v6:
            if self.network:
                self.factory = ipaddress.ip_network
            elif self.cidr:
                self.factory = ipaddress.ip_interface
            else:
                self.factory = ipaddress.ip_address
        elif self.v4:
            if self.network:
                self.factory = ipaddress.IPv4Network
            elif self.cidr:
                self.factory = ipaddress.IPv4Interface
            else:
                self.factory = ipaddress.IPv4Address
        elif self.v6:
            if self.network:
                self.factory = ipaddress.IPv6Network
            elif self.cidr:
                self.factory = ipaddress.IPv6Interface
            else:
                self.factory = ipaddress.IPv6Address
        else:
            raise ValueError("Either IPv4 or IPv6 should be allowed")

        self.allow_zone_index = kwargs.pop('allow_zone_index', False)

        super(IPAddr, self).__init__(*args, **kwargs)

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        if value:
            try:
                if self.network:
                    self.factory(value, strict=self.network_strict)
                else:
                    if self.cidr and '/' not in value:
                        raise ValueError(
                            'Specified address should be in CIDR notation, e.g. 192.168.0.2/24'
                        )

                    has_zone_index = False
                    if self.allow_zone_index and "%" in value:
                        has_zone_index = True
                        value = value[:value.rindex("%")]

                    addr = self.factory(value)

                    if has_zone_index and not isinstance(addr, ipaddress.IPv6Address):
                        raise ValueError("Zone index is allowed only for IPv6 addresses")
            except ValueError as e:
                verrors.add(self.name, str(e), errno.EINVAL)

        if verrors:
            raise verrors

        return super().validate(value)


class Time(Str):

    def clean(self, value):
        if isinstance(value, time):
            return value

        value = super(Time, self).clean(value)
        if value is None:
            return value

        try:
            hours, minutes = value.split(':')
        except ValueError:
            raise ValueError('Time should be in 24 hour format like "18:00"')
        else:
            try:
                return time(int(hours), int(minutes))
            except TypeError:
                raise ValueError('Time should be in 24 hour format like "18:00"')

    def validate(self, value):
        return super().validate(str(value))


class Datetime(Str):

    def clean(self, value):
        if isinstance(value, datetime):
            return value
        value = super().clean(value)
        if value is None:
            return value
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError):
            raise ValueError('Invalid datetime specified')

    def validate(self, value):
        return super().validate(str(value))


class UnixPerm(Str):

    def validate(self, value):
        if value is None:
            return

        try:
            mode = int(value, 8)
        except ValueError:
            raise ValueError('Not a valid integer. Must be between 000 and 777')

        if mode & 0o777 != mode:
            raise ValueError('Please supply a value between 000 and 777')

        return super().validate(value)


class Bool(Attribute):

    def clean(self, value):
        value = super().clean(value)
        if value is None:
            return value
        if not isinstance(value, bool):
            raise Error(self.name, 'Not a boolean')
        return value

    def to_json_schema(self, parent=None):
        return {
            'type': ['boolean', 'null'] if self.null else 'boolean',
            **self._to_json_schema_common(parent),
        }


class Int(EnumMixin, Attribute):

    def clean(self, value):
        value = super(Int, self).clean(value)
        if value is None:
            return value
        if not isinstance(value, int) or isinstance(value, bool):
            if isinstance(value, str) and value.isdigit():
                return int(value)
            raise Error(self.name, 'Not an integer')
        return value

    def to_json_schema(self, parent=None):
        return {
            'type': ['integer', 'null'] if self.null else 'integer',
            **self._to_json_schema_common(parent),
        }


class Float(EnumMixin, Attribute):

    def clean(self, value):
        value = super(Float, self).clean(value)
        if value is None and not self.required:
            return self.default
        try:
            # float(False) = 0.0
            # float(True) = 1.0
            if isinstance(value, bool):
                raise TypeError()
            return float(value)
        except (TypeError, ValueError):
            raise Error(self.name, 'Not a floating point number')

    def to_json_schema(self, parent=None):
        return {
            'type': ['float', 'null'] if self.null else 'float',
            **self._to_json_schema_common(parent),
        }


class List(EnumMixin, Attribute):

    def __init__(self, *args, **kwargs):
        self.items = kwargs.pop('items', [])
        self.unique = kwargs.pop('unique', False)
        if 'default' not in kwargs:
            kwargs['default'] = []
        super(List, self).__init__(*args, **kwargs)

    def clean(self, value):
        value = super(List, self).clean(value)
        if value is None:
            return copy.deepcopy(self.default)
        if not isinstance(value, list):
            raise Error(self.name, 'Not a list')
        if not self.empty and not value:
            raise Error(self.name, 'Empty value not allowed')
        if self.items:
            for index, v in enumerate(value):
                for i in self.items:
                    try:
                        tmpval = copy.deepcopy(v)
                        value[index] = i.clean(tmpval)
                        found = True
                        break
                    except (Error, ValidationErrors) as e:
                        found = e
                if self.items and found is not True:
                    raise Error(self.name, 'Item#{0} is not valid per list types: {1}'.format(index, found))
        return value

    def has_private(self):
        return self.private or any(item.has_private() for item in self.items)

    def dump(self, value):
        if self.has_private():
            return '********'
        return value

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        s = set()
        for i, v in enumerate(value):
            if self.unique:
                if isinstance(v, dict):
                    v = tuple(sorted(list(v.items())))
                if v in s:
                    verrors.add(f"{self.name}.{i}", "This value is not unique.")
                s.add(v)
            attr_verrors = ValidationErrors()
            for attr in self.items:
                try:
                    attr.validate(v)
                except ValidationErrors as e:
                    attr_verrors.add_child(f"{self.name}.{i}", e)
                else:
                    break
            else:
                verrors.extend(attr_verrors)

        if verrors:
            raise verrors

        super().validate(value)

    def to_json_schema(self, parent=None):
        schema = self._to_json_schema_common(parent)
        if self.null:
            schema['type'] = ['array', 'null']
        else:
            schema['type'] = 'array'
        schema['items'] = [i.to_json_schema(self) for i in self.items]
        return schema

    def resolve(self, schemas):
        for index, i in enumerate(self.items):
            if not i.resolved:
                self.items[index] = i.resolve(schemas)
        if self.register:
            schemas.add(self)
        self.resolved = True
        return self

    def copy(self):
        cp = super().copy()
        cp.items = []
        for item in self.items:
            cp.items.append(item.copy())
        return cp


class Dict(Attribute):

    def __init__(self, *attrs, **kwargs):
        # TODO: Let's please perhaps have name as a keyword argument when we add support for
        # optional name argument in accepts decorator
        if list(attrs) and isinstance(attrs[0], str):
            name = attrs[0]
            attrs = list(attrs[1:])
        else:
            name = ''
        self.additional_attrs = kwargs.pop('additional_attrs', False)
        self.conditional_defaults = kwargs.pop('conditional_defaults', {})
        self.strict = kwargs.pop('strict', False)
        # Update property is used to disable requirement on all attributes
        # as well to not populate default values for not specified attributes
        self.update = kwargs.pop('update', False)
        if 'default' not in kwargs:
            kwargs['default'] = {}
        super(Dict, self).__init__(name, **kwargs)

        self.attrs = {}
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
                        raise ValueError(f"Attribute {attr.name} is required and has default value at the same time, "
                                         f"this is forbidden in strict mode")
                else:
                    if not attr.has_default:
                        raise ValueError(f"Attribute {attr.name} is not required and does not have default value, "
                                         f"this is forbidden in strict mode")

    def has_private(self):
        return self.private or any(i.has_private() for i in self.attrs.values())

    def get_attrs_to_skip(self, data):
        skip_attrs = defaultdict(set)
        check_data = self.get_defaults(data, {}, ValidationErrors(), False) if not self.update else data
        for attr, attr_data in filter(
            lambda k: not filter_list([check_data], k[1]['filters']), self.conditional_defaults.items()
        ):
            for k in attr_data['attrs']:
                skip_attrs[k].update({attr})

        return skip_attrs

    def clean(self, data):
        data = super().clean(data)

        if data is None:
            if self.null:
                return None

            return copy.deepcopy(self.default)

        if not isinstance(data, dict):
            raise Error(self.name, 'A dict was expected')

        verrors = ValidationErrors()
        for key, value in list(data.items()):
            if not self.additional_attrs:
                if key not in self.attrs:
                    verrors.add(f'{self.name}.{key}', 'Field was not expected')
                    continue

            attr = self.attrs.get(key)
            if not attr:
                continue

            data[key] = self._clean_attr(attr, value, verrors)

        # Do not make any field and required and not populate default values
        if not self.update:
            data.update(self.get_defaults(data, self.get_attrs_to_skip(data), verrors))

        verrors.check()

        return data

    def get_defaults(self, orig_data, skip_attrs, verrors, check_required=True):
        data = copy.deepcopy(orig_data)
        for attr in list(self.attrs.values()):
            if attr.name not in data and attr.name not in skip_attrs and (
                (check_required and attr.required) or attr.has_default
            ):
                data[attr.name] = self._clean_attr(attr, NOT_PROVIDED, verrors)
        return data

    def _clean_attr(self, attr, value, verrors):
        try:
            return attr.clean(value)
        except Error as e:
            verrors.add(f'{self.name}.{e.attribute}', e.errmsg, e.errno)
        except ValidationErrors as e:
            verrors.extend(e)

    def dump(self, value):
        if self.private:
            return "********"

        if not isinstance(value, dict):
            return value

        value = value.copy()
        for key in value:
            attr = self.attrs.get(key)
            if not attr:
                continue

            value[key] = attr.dump(value[key])

        return value

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        for attr in self.attrs.values():
            if attr.name in value:
                try:
                    attr.validate(value[attr.name])
                except ValidationErrors as e:
                    verrors.add_child(self.name, e)

        if verrors:
            raise verrors

    def to_json_schema(self, parent=None):
        schema = {
            'type': 'object',
            'properties': {},
            'additionalProperties': self.additional_attrs,
            **self._to_json_schema_common(parent),
        }
        for name, attr in list(self.attrs.items()):
            schema['properties'][name] = attr.to_json_schema(parent=self)
        schema['_attrs_order_'] = list(self.attrs.keys())
        return schema

    def resolve(self, schemas):
        for name, attr in list(self.attrs.items()):
            if not attr.resolved:
                new_name = attr.newname if isinstance(attr, Patch) else name
                self.attrs[new_name] = attr.resolve(schemas)
                if new_name != name:
                    self.attrs.pop(name)
        if self.register:
            schemas.add(self)
        self.resolved = True
        return self

    def copy(self):
        cp = super().copy()
        cp.attrs = {}
        for name, attr in self.attrs.items():
            cp.attrs[name] = attr.copy()
        return cp


class Cron(Dict):

    FIELDS = ['minute', 'hour', 'dom', 'month', 'dow']

    def __init__(self, name='', **kwargs):
        self.additional_attrs = kwargs.pop('additional_attrs', False)
        exclude = kwargs.pop('exclude', [])
        defaults = kwargs.pop('defaults', {})
        self.begin_end = kwargs.pop('begin_end', False)
        # Update property is used to disable requirement on all attributes
        # as well to not populate default values for not specified attributes
        self.update = kwargs.pop('update', False)
        super(Cron, self).__init__(name, **kwargs)
        self.attrs = {}
        for i in filter(lambda f: f not in exclude, Cron.FIELDS):
            self.attrs[i] = Str(i, default=defaults.get(i, '*'))
        if self.begin_end:
            self.attrs['begin'] = Time('begin', default=defaults.get('begin', '00:00'))
            self.attrs['end'] = Time('end', default=defaults.get('end', '23:59'))

    @staticmethod
    def convert_schedule_to_db_format(data_dict, schedule_name='schedule', key_prefix='', begin_end=False):
        if schedule_name in data_dict:
            schedule = data_dict.pop(schedule_name)
            db_fields = ['minute', 'hour', 'daymonth', 'month', 'dayweek']
            if schedule is not None:
                for index, field in enumerate(Cron.FIELDS):
                    if field in schedule:
                        data_dict[key_prefix + db_fields[index]] = schedule[field]
                if begin_end:
                    for field in ['begin', 'end']:
                        if field in schedule:
                            data_dict[key_prefix + field] = schedule[field]
            else:
                for index, field in enumerate(Cron.FIELDS):
                    data_dict[key_prefix + db_fields[index]] = None
                if begin_end:
                    for field in ['begin', 'end']:
                        data_dict[key_prefix + field] = None

    @staticmethod
    def convert_db_format_to_schedule(data_dict, schedule_name='schedule', key_prefix='', begin_end=False):
        db_fields = ['minute', 'hour', 'daymonth', 'month', 'dayweek']
        data_dict[schedule_name] = {}
        for index, field in enumerate(db_fields):
            key = key_prefix + field
            if key in data_dict:
                value = data_dict.pop(key)
                if value is None:
                    data_dict[schedule_name] = None
                else:
                    if data_dict[schedule_name] is not None:
                        data_dict[schedule_name][Cron.FIELDS[index]] = value
        if begin_end:
            for field in ['begin', 'end']:
                key = key_prefix + field
                if key in data_dict:
                    value = data_dict.pop(key)
                    if value is None:
                        data_dict[schedule_name] = None
                    else:
                        if data_dict[schedule_name] is not None:
                            data_dict[schedule_name][field] = str(value)[:5]

    def validate(self, value):
        if value is None:
            return

        verrors = ValidationErrors()

        for attr in self.attrs.values():
            if attr.name in value:
                try:
                    attr.validate(value[attr.name])
                except ValidationErrors as e:
                    verrors.add_child(self.name, e)

        for v in value:
            if self.begin_end and v in ['begin', 'end']:
                continue
            if v not in Cron.FIELDS:
                verrors.add(self.name, f'Unexpected {v} value')

        if verrors:
            raise verrors

        cron_expression = ''
        for field in Cron.FIELDS:
            cron_expression += value.get(field) + ' ' if value.get(field) else '* '

        try:
            iter = croniter(cron_expression)
        except Exception as e:
            iter = None
            verrors.add(self.name, 'Please ensure fields match cron syntax - ' + str(e))

        if value.get('begin') and value.get('end') and not (value.get('begin') <= value.get('end')):
            verrors.add(self.name, 'Begin time should be less or equal than end time')

        if iter is not None and (value.get('begin') or value.get('end')):
            begin = value.get('begin') or time(0, 0)
            end = value.get('end') or time(23, 59)
            for i in range(24 * 60):
                d = iter.get_next(datetime)
                if begin <= d.time() <= end:
                    break
            else:
                verrors.add(self.name, 'Specified schedule does not match specified time interval')

        if verrors:
            raise verrors


class Ref(object):

    def __init__(self, name):
        self.name = name
        self.resolved = False

    def resolve(self, schemas):
        schema = schemas.get(self.name)
        if not schema:
            raise ResolverError('Schema {0} does not exist'.format(self.name))
        schema = schema.copy()
        schema.register = False
        schema.resolved = True
        self.resolved = True
        return schema


class Patch(object):

    def __init__(self, name, newname, *patches, register=False):
        self.name = name
        self.newname = newname
        self.patches = list(patches)
        self.register = register
        self.resolved = False

    def resolve(self, schemas):
        schema = schemas.get(self.name)
        if not schema:
            raise ResolverError(f'Schema {self.name} not found')
        elif not isinstance(schema, Dict):
            raise ValueError('Patch non-dict is not allowed')

        schema = schema.copy()
        schema.name = self.newname
        for operation, patch in self.patches:
            if operation == 'replace':
                # This is for convenience where it's hard sometimes to change attrs in a large dict
                # with custom function(s) outlining the operation - it's easier to just replace the attr
                name = patch['name'] if isinstance(patch, dict) else patch.name
                self._resolve_internal(schema, schemas, 'rm', {'name': name})
                operation = 'add'
            self._resolve_internal(schema, schemas, operation, patch)
        if self.register:
            schemas.add(schema)
        schema.resolved = True
        self.resolved = True
        return schema

    def _resolve_internal(self, schema, schemas, operation, patch):
        if operation == 'add':
            if isinstance(patch, dict):
                new = convert_schema(dict(patch))
            else:
                new = copy.deepcopy(patch)
            schema.attrs[new.name] = new
        elif operation == 'rm':
            if patch.get('safe_delete') and patch['name'] not in schema.attrs:
                return
            del schema.attrs[patch['name']]
        elif operation == 'edit':
            attr = schema.attrs[patch['name']]
            if 'method' in patch:
                patch['method'](attr)
                schema.attrs[patch['name']] = attr.resolve(schemas)
        elif operation == 'attr':
            for key, val in list(patch.items()):
                setattr(schema, key, val)


class OROperator:
    def __init__(self, *schemas, **kwargs):
        self.name = kwargs.get('name', '')
        self.title = kwargs.get('title') or self.name
        self.schemas = list(schemas)
        self.description = kwargs.get('description')
        self.resolved = False

    def clean(self, value):
        found = False
        final_value = value
        verrors = ValidationErrors()
        for index, i in enumerate(self.schemas):
            try:
                tmpval = copy.deepcopy(value)
                final_value = i.clean(tmpval)
            except (Error, ValidationErrors) as e:
                if isinstance(e, Error):
                    verrors.add(e.attribute, e.errmsg, e.errno)
                else:
                    verrors.extend(e)
            else:
                found = True
                break
        if found is not True:
            raise Error(self.name, f'Result does not match specified schema: {verrors}')
        return final_value

    def validate(self, value):
        verrors = ValidationErrors()
        attr_verrors = ValidationErrors()
        for attr in self.schemas:
            try:
                attr.validate(value)
            except TypeError:
                pass
            except ValidationErrors as e:
                attr_verrors.extend(e)
            else:
                break
        else:
            verrors.extend(attr_verrors)

        verrors.check()

    def to_json_schema(self, parent=None):
        return {
            'anyOf': [i.to_json_schema() for i in self.schemas],
            'nullable': False,
            '_name_': self.name,
            'description': self.description,
        }

    def resolve(self, schemas):
        for index, i in enumerate(self.schemas):
            if not i.resolved:
                self.schemas[index] = i.resolve(schemas)
        self.resolved = True
        return self

    def copy(self):
        cp = copy.deepcopy(self)
        cp.register = False
        return cp


class ResolverError(Exception):
    pass


def resolver(schemas, f):
    if not callable(f):
        return

    for schema_type in filter(functools.partial(hasattr, f), ('accepts', 'returns')):
        new_params = []
        schema_obj = getattr(f, schema_type)
        for p in schema_obj:
            if isinstance(p, (Patch, Ref, Attribute, OROperator)):
                resolved = p if p.resolved else p.resolve(schemas)
                new_params.append(resolved)
            else:
                raise ResolverError(f'Invalid parameter definition {p}')

        # FIXME: for some reason assigning params (f.accepts = new_params) does not work
        schema_obj.clear()
        schema_obj.extend(new_params)


def resolve_methods(schemas, to_resolve):
    while len(to_resolve) > 0:
        resolved = 0
        for method in list(to_resolve):
            try:
                resolver(schemas, method)
            except ResolverError:
                pass
            else:
                to_resolve.remove(method)
                resolved += 1
        if resolved == 0:
            raise ValueError(f'Not all schemas could be resolved: {to_resolve}')


def validate_return_type(func, result, schemas):
    if not schemas and result is None:
        return
    elif not schemas:
        raise ValueError(f'Return schema missing for {func.__name__!r}')

    result = copy.deepcopy(result)
    if not isinstance(result, tuple):
        result = [result]

    verrors = ValidationErrors()
    for res_entry, schema in zip(result, schemas):
        clean_and_validate_arg(verrors, schema, res_entry)
    verrors.check()


def clean_and_validate_arg(verrors, attr, arg):
    try:
        value = attr.clean(arg)
        attr.validate(value)
        return value
    except Error as e:
        verrors.add(e.attribute, e.errmsg, e.errno)
    except ValidationErrors as e:
        verrors.extend(e)


def returns(*schema):
    def returns_internal(f):
        if asyncio.iscoroutinefunction(f):
            async def nf(*args, **kwargs):
                res = await f(*args, **kwargs)
                if conf.debug_mode:
                    validate_return_type(f, res, nf.returns)
                return res
        else:
            def nf(*args, **kwargs):
                res = f(*args, **kwargs)
                if conf.debug_mode:
                    validate_return_type(f, res, nf.returns)
                return res

        from middlewared.utils.type import copy_function_metadata
        copy_function_metadata(f, nf)
        nf.wraps = f
        for s in list(schema):
            s.name = s.name or f.__name__
            if hasattr(s, 'title'):
                s.title = s.title or s.name
        nf.returns = list(schema)
        return nf
    return returns_internal


def accepts(*schema):
    further_only_hidden = False
    for i in schema:
        if getattr(i, 'hidden', False):
            further_only_hidden = True
        elif further_only_hidden:
            raise ValueError("You can't have non-hidden arguments after hidden")

    def wrap(func):
        f = func.wraps if hasattr(func, 'wraps') else func
        if inspect.getfullargspec(f).defaults:
            raise ValueError("All public method default arguments should be specified in @accepts()")

        # Make sure number of schemas is same as method argument
        args_index = 0
        if f.__code__.co_argcount >= 1 and f.__code__.co_varnames[0] == 'self':
            args_index += 1
        if hasattr(f, '_pass_app'):
            args_index += 1
        if hasattr(f, '_job'):
            args_index += 1
        if hasattr(f, '_skip_arg'):
            args_index += f._skip_arg
        assert len(schema) == f.__code__.co_argcount - args_index  # -1 for self

        def clean_and_validate_args(args, kwargs):
            args = list(args)
            args = args[:args_index] + copy.deepcopy(args[args_index:])
            kwargs = copy.deepcopy(kwargs)

            verrors = ValidationErrors()

            # Iterate over positional args first, excluding self
            i = 0
            for _ in args[args_index:]:
                args[args_index + i] = clean_and_validate_arg(verrors, nf.accepts[i], args[args_index + i])
                i += 1

            # Use i counter to map keyword argument to rpc positional
            for x in list(range(i + args_index, f.__code__.co_argcount)):
                kwarg = f.__code__.co_varnames[x]

                if kwarg in kwargs:
                    attr = nf.accepts[i]
                    i += 1

                    value = kwargs[kwarg]
                elif len(nf.accepts) >= i + 1:
                    attr = nf.accepts[i]
                    i += 1
                    value = NOT_PROVIDED
                else:
                    i += 1
                    continue

                kwargs[kwarg] = clean_and_validate_arg(verrors, attr, value)

            if verrors:
                raise verrors

            return args, kwargs

        if asyncio.iscoroutinefunction(func):
            async def nf(*args, **kwargs):
                args, kwargs = clean_and_validate_args(args, kwargs)
                return await func(*args, **kwargs)
        else:
            def nf(*args, **kwargs):
                args, kwargs = clean_and_validate_args(args, kwargs)
                return func(*args, **kwargs)

        from middlewared.utils.type import copy_function_metadata
        copy_function_metadata(f, nf)
        nf.accepts = list(schema)
        if hasattr(func, 'returns'):
            nf.returns = func.returns
        nf.wraps = f
        nf.wrap = wrap

        return nf

    return wrap
