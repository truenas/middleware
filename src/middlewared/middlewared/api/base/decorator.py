import asyncio
import functools
import inspect
import re
import sys
import types
import typing

from ..base.model import BaseModel
from .handler.accept import accept_params

__all__ = ["api_method", "private_method"]

from ...utils.types import AuditCallback

CONFIG_CRUD_METHODS = frozenset([
    'do_create', 'do_update', 'do_delete',
    'create', 'update', 'delete',
    'query', 'get_instance', 'config'
])
MAJOR_VERSION = re.compile(r"^v([0-9]{2})$")
ANNOTATION_PREFIX = re.compile(r"middlewared\.api\.[^.]+\.[^.]+\.")


def function_arg_names(f: types.FunctionType) -> list[str]:
    return list(f.__code__.co_varnames)[:f.__code__.co_argcount]


def process_annotation(annotation: typing.Any) -> typing.Any:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job

    if annotation == "App":
        return App
    if annotation == "AuditCallback":
        return AuditCallback
    if annotation == "Job":
        return Job

    return annotation


def calculate_args_index(f: typing.Any, audit_callback: bool, check_annotations: bool) -> int:
    """Determine how many leading arguments are framework-injected (before user params).

    Decorators must be stacked outermost-to-innermost and the method signature must list the
    injected parameters in the following order (each is optional depending on which decorators
    are applied)::

        self, [app], [job], [audit_callback], [tls], [message_id], <user params...>

    Decorator stacking order (top to bottom)::

        @api_method(MyArgs, MyResult, roles=[...])
        @pass_app()                        # optional
        @pass_thread_local_storage         # optional, sync methods only
        @job(lock=...)                     # optional, must be innermost
        def my_method(self, app, job, tls, id_, options):
            ...

    ``@job`` must always be the innermost (bottommost) decorator so that its ``_job`` attribute
    is set on the raw function before the other decorators inspect it.  A mismatch between the
    decorator stack and the method signature is caught here at class-load time.
    """
    from middlewared.api.base.server.app import App
    from middlewared.job import Job

    signature_args = function_arg_names(f)
    # This must match the order used in `Middleware._call_prepare`
    expected_args: list[tuple[str, typing.Any]] = []
    if signature_args and signature_args[0] == 'self':
        expected_args.append(('self', None))
    if pass_app := hasattr(f, '_pass_app'):
        expected_args.append(('app', App))
    # `app` comes before `job` as defined in `Job.__run_body`
    if hasattr(f, '_job'):
        expected_args.append(('job', Job))
    if audit_callback:
        expected_args.append(('audit_callback', AuditCallback))
    if hasattr(f, '_pass_thread_local_storage'):
        expected_args.append(('tls', None))
    if pass_app and f._pass_app['message_id']:
        expected_args.append(('message_id', str))

    # FIXME: Get rid of the cases where `check_annotations` is `False`
    if check_annotations:
        signature_args_with_annotations = [
            (name, process_annotation(f.__annotations__.get(name)))
            for name in signature_args[:len(expected_args)]
        ]
        if signature_args_with_annotations[:len(expected_args)] != expected_args:
            expected = ", ".join([
                f"{name}: {annotation!r}" if annotation is not None else name
                for name, annotation in expected_args
            ])
            signature = inspect.signature(f)
            found = ", ".join([str(signature.parameters[name]) for name in signature_args])
            raise RuntimeError(
                f"Invalid method signature for {f!r}. Its arguments list must start with {expected!r}. "
                f"It is {found!r}"
            )
    else:
        expected_args_names = [name for name, _ in expected_args]
        if signature_args[:len(expected_args)] != expected_args_names:
            expected = ", ".join(expected_args_names)
            raise RuntimeError(
                f"Invalid method signature for {f!r}. Its arguments list must start with {expected!r}. "
                f"It is {', '.join(signature_args)!r}"
            )

    args_index = len(expected_args)
    if hasattr(f, '_skip_arg'):
        args_index += f._skip_arg
    return args_index


def api_method[**P, T](
    accepts: type[BaseModel],
    returns: type[BaseModel],
    *,
    audit: str | None = None,
    audit_callback: bool = False,
    audit_extended: typing.Callable[..., str] | None = None,
    rate_limit: bool = True,
    roles: list[str] | None = None,
    private: bool = False,
    cli_private: bool = False,
    authentication_required: bool = True,
    authorization_required: bool = True,
    pass_app: bool = False,
    pass_app_require: bool = False,
    pass_thread_local_storage: bool = False,
    skip_args: int | None = None,
    removed_in: str | None = None,
    check_annotations: bool = False,  # FIXME: Eventually must be `True` for all api methods.
) -> typing.Callable[[typing.Callable[P, T]], typing.Callable[P, T]]:
    """
    Mark a `Service` class method as an API method.

    `accepts` and `returns` are classes derived from `BaseModel` that correspond to the method's call arguments and
    return value.

    `audit` is the message that will be logged to the audit log when the decorated function is called.

    If `audit_callback` is `True` then an additional `audit_callback` argument will be prepended to the function
    arguments list. This callback must be called with a single string argument that will be appended to the audit
    message to be logged.

    `audit_extended` is the function that takes the same arguments as the decorated function and returns the string
    that will be appended to the audit message to be logged.

    `rate_limit` specifies whether the method calls should be rate limited when calling without authentication.

    `roles` is a list of user roles that will gain access to this method.

    `private` is `True` when the method should not be exposed in the public API. By default, the method is public.

    `cli_private` is `True` when the method should not be exposed in the CLI. By default, the method is public.

    `authentication_required` is False when API endpoint does not require authentication. This should generally
    *not* be set and requires appropriate review and approval to validate that its use complies with security
    standards. This is incompatible with `roles`.

    `authorization_required` is False API endpoint does not require authorization, but does require authentication.
    This is incompatible with `roles`. Additional review will be required in order to validate that its use complies
    with security standards.

    `pass_thread_local_storage` if set to True, will inject a thread-local storage object as an argument to the
    decorated method. NOTE: this is using a traditional threading.local() object and not a ContextVar so the
    method must be a non-coroutine based method/function.

    `removed_in` specifies major TrueNAS version (in the format vXX) which removes this API method.
    """
    return decorator(
        accepts,
        returns,
        audit,
        audit_callback,
        audit_extended,
        rate_limit,
        roles,
        private,
        cli_private,
        authentication_required,
        authorization_required,
        pass_app,
        pass_app_require,
        pass_thread_local_storage,
        skip_args,
        removed_in,
        check_annotations,
    )


def private_method[**P, T](
    pass_app: bool = False,
    pass_app_require: bool = False,
    pass_thread_local_storage: bool = False,
    check_annotations: bool = False,  # FIXME: Eventually must be `True` for all api methods.
) -> typing.Callable[[typing.Callable[P, T]], typing.Callable[P, T]]:
    return decorator(
        accepts=None,
        returns=None,
        audit=None,
        audit_callback=False,
        audit_extended=None,
        rate_limit=True,
        roles=None,
        private=True,
        cli_private=True,
        authentication_required=True,
        authorization_required=True,
        pass_app=pass_app,
        pass_app_require=pass_app_require,
        pass_thread_local_storage=pass_thread_local_storage,
        skip_args=None,
        removed_in=None,
        check_annotations=check_annotations,
    )


def decorator[**P, T](
    accepts: type[BaseModel] | None,
    returns: type[BaseModel] | None,
    audit: str | None,
    audit_callback: bool,
    audit_extended: typing.Callable[..., str] | None,
    rate_limit: bool,
    roles: list[str] | None,
    private: bool,
    cli_private: bool,
    authentication_required: bool,
    authorization_required: bool,
    pass_app: bool,
    pass_app_require: bool,
    pass_thread_local_storage: bool,
    skip_args: int | None,
    removed_in: str | None,
    check_annotations: bool,
) -> typing.Callable[[typing.Callable[P, T]], typing.Callable[P, T]]:
    if accepts is not None and returns is not None:
        if list(returns.model_fields.keys()) != ["result"]:
            raise TypeError("`returns` model must only have one field called `result`")

        check_model_module(accepts, private)
        check_model_module(returns, private)

    def wrapper(func: typing.Callable[P, T]) -> typing.Callable[P, T]:
        if pass_app:
            # Pass the application instance as parameter to the method
            func._pass_app = {  # type: ignore[attr-defined]
                'message_id': False,
                'require': pass_app_require,
            }
        if pass_thread_local_storage:
            func._pass_thread_local_storage = True  # type: ignore[attr-defined]

        if skip_args is not None:
            func._skip_arg = skip_args  # type: ignore[attr-defined]

        args_index = calculate_args_index(func, audit_callback, check_annotations)

        if accepts is not None and returns is not None:
            dump_models = True
            if check_annotations:
                check_method_annotations(
                    func,  # type: ignore[arg-type]
                    args_index,
                    accepts,
                    returns,
                )
                dump_models = False

            if asyncio.iscoroutinefunction(func):
                if pass_thread_local_storage:
                    raise ValueError('pass_thread_local_storage invalid for coroutines')

                @functools.wraps(func)
                async def wrapped(*args: typing.Any) -> T:
                    args2 = list(args[:args_index]) + accept_params(accepts, args[args_index:], dump_models=dump_models)

                    result = await func(*args2)  # type: ignore[call-arg]

                    return result  # type: ignore[no-any-return]
            else:
                @functools.wraps(func)
                def wrapped(*args: typing.Any) -> T:
                    args2 = list(args[:args_index]) + accept_params(accepts, args[args_index:], dump_models=dump_models)

                    result = func(*args2)  # type: ignore[call-arg]

                    return result
        else:
            wrapped = func  # type: ignore[assignment]

        if private:
            if roles or not authentication_required or not authorization_required:
                raise ValueError('Cannot set roles, no authorization, or no authentication on private methods.')

        elif roles:
            if not authorization_required or not authentication_required:
                raise ValueError('Authentication and authorization must be enabled in order to use roles.')

        elif not authorization_required:
            if not authentication_required:
                # Although this is technically valid the concern is that dev has fat-fingered something
                raise ValueError('Either authentication or authorization may be disabled, but not both simultaneously.')
            wrapped._no_authz_required = True  # type: ignore[attr-defined]

        elif not authentication_required:
            wrapped._no_auth_required = True  # type: ignore[attr-defined]

        elif func.__name__ not in CONFIG_CRUD_METHODS and not func.__name__.endswith('choices'):
            # All public methods should have a roles definition. This is a rough check to help developers not write
            # methods that are only accesssible to full_admin. We don't bother checking CONFIG and CRUD methods
            # and choices because they may have implicit roles through the role_prefix configuration.
            raise ValueError(f'{func.__name__}: Role definition is required for public API endpoints')

        wrapped.audit = audit  # type: ignore[attr-defined]
        wrapped.audit_callback = audit_callback  # type: ignore[attr-defined]
        wrapped.audit_extended = audit_extended  # type: ignore[attr-defined]
        wrapped.rate_limit = rate_limit  # type: ignore[attr-defined]
        wrapped.roles = roles or []  # type: ignore[attr-defined]
        wrapped._private = private  # type: ignore[attr-defined]
        wrapped._cli_private = cli_private  # type: ignore[attr-defined]
        if removed_in is not None:
            if not MAJOR_VERSION.match(removed_in):
                raise ValueError(
                    f'{func.__name__}: removed_in must be a valid major TrueNAS version number in the format vXX'
                )

            wrapped._removed_in = removed_in  # type: ignore[attr-defined]

        if accepts is not None and returns is not None:
            wrapped.new_style_accepts = accepts  # type: ignore[attr-defined]
            wrapped.new_style_returns = returns  # type: ignore[attr-defined]

        return wrapped  # type: ignore[return-value]

    return wrapper


def check_model_module(model: type[BaseModel], private: bool) -> None:
    module_name = model.__module__

    # CRUDService and ConfigService dynamically generate models.
    if module_name in (
        "middlewared.plugins.test.pipes", "middlewared.service.crud_service", "middlewared.service.config_service"
    ):
        return

    if private:
        if model.__name__ == "QueryArgs" or model.__name__.endswith("QueryResult"):
            # `filterable_api_method`
            return

        if module_name.startswith("middlewared.api."):
            raise ValueError(
                "Private methods must have their accepts/returns models defined in the corresponding plugin class. "
                f"{model.__name__} is defined in {module_name}."
            )
    else:
        if not module_name.startswith("middlewared.api."):
            raise ValueError(
                "Public methods must have their accepts/returns models defined in middlewared.api package. "
                f"{model.__name__} is defined in {module_name}."
            )


def _resolve_annotation(func: types.FunctionType, name: str) -> typing.Any:
    """Resolve a function's annotation by name into a real type.

    With `from __future__ import annotations`, annotations are stored as strings.
    This evaluates them using the function's module globals so that normalize_annotation
    can decompose unions and generics.
    Returns the annotation unchanged if it is already a real type (no __future__).
    """
    annotation = func.__annotations__.get(name)
    if isinstance(annotation, str):
        return eval(annotation, vars(sys.modules[func.__module__]))
    return annotation


def check_method_annotations(
    func: types.FunctionType, args_index: int, accepts: type[BaseModel], returns: type[BaseModel]
) -> None:
    expected_args = [(name, field.annotation) for name, field in accepts.model_fields.items()]
    # Resolve string annotations (from `from __future__ import annotations`) into real types
    # so that normalize_annotation can decompose them via union/generic recursion.
    # We only resolve the params we actually check (after args_index) plus the return type,
    # because framework-injected params (e.g. app: App) may reference TYPE_CHECKING-only imports.
    func_args = [
        (name, _resolve_annotation(func, name))
        for name in function_arg_names(func)[args_index:]
    ]
    # We only compare annotations since we don't care about parameter names.
    expected_annotations = [normalize_annotation(annotation) for _, annotation in expected_args]
    func_annotations = [normalize_annotation(annotation) for _, annotation in func_args]

    # When a model field has a default, allow the function to annotate `T | None`
    # even though the model field is just `T`.
    for i, (name, _) in enumerate(expected_args):
        field = accepts.model_fields[name]
        if (
            i < len(func_annotations)
            and not field.is_required()
            and func_annotations[i] == f"{expected_annotations[i]} | None"
        ):
            func_annotations[i] = expected_annotations[i]

    if expected_annotations != func_annotations:
        expected = ", ".join([
            f"{name}: {annotation}" if annotation is not None else name
            for name, annotation in expected_args
        ])
        signature = inspect.signature(func)
        found = ", ".join([str(signature.parameters[name]) for name, _ in func_args])
        raise ValueError(f"{func.__name__}: must have the following signature: {expected!r}. "
                         f"Got {found!r}.")

    expected_return_annotation = normalize_annotation(returns.model_fields["result"].annotation, returns)
    return_annotation = normalize_annotation(_resolve_annotation(func, "return"), returns)
    if return_annotation != expected_return_annotation:
        raise ValueError(f"{func.__name__}: must have a `return` annotation of {expected_return_annotation!r}. "
                         f"Got {return_annotation!r}.")


def normalize_annotation(annotation: typing.Any, parent_model: type[BaseModel] | None = None) -> str | None:
    origin = typing.get_origin(annotation)

    # Recurse into union members (handles both `X | Y` and `typing.Union[X, Y]`)
    if origin is types.UnionType or origin is typing.Union:
        args = typing.get_args(annotation)
        normalized = [normalize_annotation(arg, parent_model) for arg in args]
        non_none = [a for a in normalized if a is not None]
        has_none = None in normalized
        if not non_none:
            return None
        result = " | ".join(sorted(set(non_none)))
        if has_none:
            result += " | None"
        return result

    # Recurse into generic type arguments (e.g., list[X] -> normalize X)
    if (
        origin is not None
        and origin is not types.UnionType
        and origin is not typing.Union
        and origin is not typing.Annotated
        and origin is not typing.Literal
    ):
        args = typing.get_args(annotation)
        if args:
            normalized_args = [normalize_annotation(arg, parent_model) for arg in args]
            origin_name = origin.__name__ if isinstance(origin, type) else repr(origin)
            return f"{origin_name}[{', '.join(str(a) for a in normalized_args)}]"

    result_annotation = annotation
    if origin is typing.Annotated:
        result_annotation = typing.get_args(annotation)[0]
    elif parent_model is not None and isinstance(annotation, typing.ForwardRef):
        result_annotation = annotation._evaluate(globals(), sys.modules[parent_model.__module__].__dict__,
                                                 recursive_guard=frozenset())

    # Allow types to declare their annotation-check equivalent
    if isinstance(result_annotation, type) and hasattr(result_annotation, '__normalize_as__'):
        result_annotation = result_annotation.__normalize_as__

    if result_annotation is None or result_annotation is type(None) or result_annotation == "None":
        return None
    elif result_annotation is bool:
        return "bool"
    elif isinstance(result_annotation, str):
        return result_annotation
    else:
        if isinstance(result_annotation, type):
            result = result_annotation.__name__
        else:
            result = repr(result_annotation)

        result = re.sub(ANNOTATION_PREFIX, "", result)
        result = result.replace("typing.", "")
        return result
