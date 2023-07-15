import asyncio
import contextlib
import copy
import json
import string
import textwrap
import warnings
from collections import defaultdict
from datetime import datetime, time, timezone
from ldap import dn
import errno
import inspect
import ipaddress
import os
import pprint
from urllib.parse import urlparse
import wbclient

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.settings import conf
from middlewared.utils import filter_list
from middlewared.utils.cron import CRON_FIELDS, croniter_for_schedule


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
        if not isinstance(value, (list, tuple)):
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
        if self.private:
            return REDACTED_VALUE

        # No schema is specified for list items or a schema is specified but
        # does not contain any private values. In this situation it's safe to
        # simply dump the raw value
        if not self.items or not self.has_private():
            return value

        # In most cases we'll only have a single item and so avoid validation loop
        if len(self.items) == 1:
            return [self.items[0].dump(x) for x in value]

        # This is painful and potentially expensive. It would probably be best
        # if developers simply avoided designing APIs in this way.
        out_list = []
        for i in value:
            # Initialize the entry value to "private"
            # If for some reason we can't validate the item then obscure the entry
            # to prevent chance of accidental exposure of private data
            entry = REDACTED_VALUE
            for item in self.items:
                # the item.clean() method may alter the value and so we need to
                # make a deepcopy of it before validation
                to_validate = copy.deepcopy(i)
                try:
                    to_validate = item.clean(to_validate)
                    item.validate(to_validate)
                except Exception:
                    continue

                # Check whether we've already successfully validated this entry
                if entry != REDACTED_VALUE:
                    # more than one of schemas fit this bill.
                    # fail safe and make it private
                    entry = REDACTED_VALUE
                    break

                # dump the original value and not the one that has been cleaned
                entry = item.dump(i)

            out_list.append(entry)

        return out_list

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

        verrors.check()

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
            verrors.add_child(self.name, e)

    def dump(self, value):
        if self.private:
            return REDACTED_VALUE

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

        verrors.check()

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
                new_name = name
                self.attrs[new_name] = attr.resolve(schemas)
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

    FIELDS = CRON_FIELDS

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

        verrors.check()

        try:
            iter = croniter_for_schedule(value)
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

        verrors.check()


class Ref(object):

    def __init__(self, name, new_name=None):
        self.schema_name = name
        self.name = new_name or name
        self.resolved = False

    def resolve(self, schemas):
        schema = schemas.get(self.schema_name)
        if not schema:
            raise ResolverError('Schema {0} does not exist'.format(self.schema_name))
        schema = schema.copy()
        schema.name = self.name
        schema.register = False
        schema.resolved = True
        self.resolved = True
        return schema

    def copy(self):
        return copy.deepcopy(self)


class Patch(object):

    def __init__(self, orig_name, newname, *patches, register=False):
        self.schema_name = orig_name
        self.name = newname
        self.patches = list(patches)
        self.register = register
        self.resolved = False

    def resolve(self, schemas):
        schema = schemas.get(self.schema_name)
        if not schema:
            raise ResolverError(f'Schema {self.schema_name} not found')
        elif not isinstance(schema, Dict):
            raise ValueError('Patch non-dict is not allowed')

        schema = schema.copy()
        schema.name = self.name
        if hasattr(schema, "title"):
            schema.title = self.name
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
        self.default = kwargs.get('default', None)
        self.has_default = 'default' in kwargs and kwargs['default'] is not NOT_PROVIDED
        self.private = kwargs.get('private', False)

    @property
    def required(self):
        for schema in filter(lambda s: hasattr(s, 'required'), self.schemas):
            if schema.required:
                return True
        return False

    def clean(self, value):
        if self.has_default and value == self.default:
            return copy.deepcopy(self.default)

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
            '_required_': self.required,
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

    def dump(self, value):
        value = copy.deepcopy(value)

        for schema in self.schemas:
            try:
                schema.clean(copy.deepcopy(value))
            except (Error, ValidationErrors):
                pass
            else:
                value = schema.dump(value)
                break

        return value

    def has_private(self):
        return self.private or any(schema.has_private() for schema in self.schemas)


class ResolverError(Exception):
    pass


def resolver(schemas, obj):
    if not isinstance(obj, dict) or not all(k in obj for k in ('keys', 'get_attr', 'has_key')):
        return

    for schema_type in filter(obj['has_key'], obj['keys']):
        new_params = []
        schema_obj = obj['get_attr'](schema_type)
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
        errors = []
        for method in list(to_resolve):
            try:
                resolver(schemas, method)
            except ResolverError as e:
                errors.append((method, e))
            else:
                to_resolve.remove(method)
                resolved += 1
        if resolved == 0:
            raise ValueError(f'Not all schemas could be resolved:\n{pprint.pformat(errors)}')


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


def accepts(*schema, deprecated=None, roles=None):
    """
    `deprecated` is a list of pairs of functions that will adapt legacy method call signatures.

    `roles` is a list of user roles that will gain access to this method.

    First member of pair is a function that accepts a list of args and returns `True` if a legacy method call
    matching a specific legacy signature was detected.
    Second member of pair is a function that accepts detected legacy arguments and returns a list of arguments
    for newer signature.
    All pairs are executed sequentially so first pair can adapt from API 2.0 to API 2.1, second from API 2.1
    to API 2.2 and so on.

    Example:

        @accepts(
            Dict("options"),
            deprecated=[
                (
                    lambda args: len(args) == 2,
                    lambda option1, option2: [{
                        "option1": option1,
                        "option2": option2,
                    }]
                )
            ],
        )

        Here an old-style method call `method("a", "b")` will be adapted to a new-style `method({"option1": "a",
                                                                                                 "option2": "b"})`
    """
    deprecated = deprecated or []

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

            common_args = args[:args_index]
            signature_args = args[args_index:]

            had_warning = False
            for check, adapt in deprecated:
                if check(signature_args):
                    if not had_warning:
                        warnings.warn(f"Method {f!r} was called with a deprecated signature", DeprecationWarning)
                        had_warning = True
                    signature_args = adapt(*signature_args)

            args = common_args + copy.deepcopy(signature_args)
            kwargs = copy.deepcopy(kwargs)

            verrors = ValidationErrors()

            # Iterate over positional args first, excluding self
            i = 0
            if len(args[args_index:]) > len(nf.accepts):
                raise CallError(f'Too many arguments (expected {len(nf.accepts)}, found {len(args[args_index:])})')
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

            verrors.check()

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
        nf.roles = roles or []
        nf.wraps = f
        nf.wrap = wrap

        return nf

    return wrap
