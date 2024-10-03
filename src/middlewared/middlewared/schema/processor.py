import asyncio
import copy
import inspect
import typing
import warnings

from middlewared.schema import Attribute
from middlewared.service_exception import CallError, ValidationErrors

from .exceptions import Error
from .utils import NOT_PROVIDED


def clean_and_validate_arg(verrors: ValidationErrors, attr: Attribute, arg):
    try:
        value = attr.clean(arg)
        attr.validate(value)
        return value
    except Error as e:
        verrors.add(e.attribute, e.errmsg, e.errno)
    except ValidationErrors as e:
        verrors.extend(e)


def validate_return_type(func, result, schemas: typing.Iterable[Attribute]):
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


def returns(*schema):
    if len(schema) > 1:
        raise ValueError("Multiple schemas for @returns are not allowed")

    def returns_internal(f):
        if asyncio.iscoroutinefunction(f):
            async def nf(*args, **kwargs):
                res = await f(*args, **kwargs)
                return res
        else:
            def nf(*args, **kwargs):
                res = f(*args, **kwargs)
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


def accepts(*schema, audit=None, audit_callback=False, audit_extended=None, deprecated=None, roles=None):
    """
    `audit` is the message that will be logged to the audit log when the decorated function is called

    `audit_extended` is the function that takes the same arguments as the decorated function and returns the string
    that will be appended to the audit message to be logged.

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
            raise ValueError('You can\'t have non-hidden arguments after hidden')

    def wrap(func):
        f = func.wraps if hasattr(func, 'wraps') else func
        if inspect.getfullargspec(f).defaults:
            raise ValueError('All public method default arguments should be specified in @accepts()')

        # Make sure number of schemas is same as method argument
        args_index = calculate_args_index(f, audit_callback)
        assert len(schema) == f.__code__.co_argcount - args_index  # -1 for self

        def clean_and_validate_args(args, kwargs):
            args = list(args)

            common_args = args[:args_index]
            signature_args = args[args_index:]

            had_warning = False
            for check, adapt in deprecated:
                if check(signature_args):
                    if not had_warning:
                        warnings.warn(f'Method {f!r} was called with a deprecated signature', DeprecationWarning)
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
        nf.audit = audit
        nf.audit_callback = audit_callback
        nf.audit_extended = audit_extended
        nf.roles = roles or []
        nf.wraps = f
        nf.wrap = wrap

        return nf

    return wrap


def calculate_args_index(f, audit_callback):
    args_index = 0
    if f.__code__.co_argcount >= 1 and f.__code__.co_varnames[0] == 'self':
        args_index += 1
    if hasattr(f, '_pass_app'):
        args_index += 1
    if audit_callback:
        args_index += 1
    if hasattr(f, '_job'):
        args_index += 1
    if hasattr(f, '_skip_arg'):
        args_index += f._skip_arg
    return args_index
