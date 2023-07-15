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
