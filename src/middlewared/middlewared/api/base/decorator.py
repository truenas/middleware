import asyncio
import functools
import re
from typing import Callable

from .handler.accept import accept_params
from ..base.model import BaseModel
from middlewared.schema.processor import calculate_args_index

__all__ = ["api_method"]


CONFIG_CRUD_METHODS = frozenset([
    'do_create', 'do_update', 'do_delete',
    'create', 'update', 'delete',
    'query', 'get_instance', 'config'
])
MAJOR_VERSION = re.compile(r"^v([0-9]{2})\.([0-9]{2})$")


def api_method(
    accepts: type[BaseModel],
    returns: type[BaseModel],
    *,
    audit: str | None = None,
    audit_callback: bool = False,
    audit_extended: Callable[..., str] | None = None,
    rate_limit=True,
    roles: list[str] | None = None,
    private: bool = False,
    cli_private: bool = False,
    authentication_required: bool = True,
    authorization_required: bool = True,
    pass_app: bool = False,
    pass_app_require: bool = False,
    pass_app_rest: bool = False,
    pass_thread_local_storage: bool = False,
    skip_args: int | None = None,
    removed_in: str | None = None,
):
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

    `removed_in` specifies major TrueNAS version (in the format vXX.YY) which removes this API method.
    """
    if list(returns.model_fields.keys()) != ["result"]:
        raise TypeError("`returns` model must only have one field called `result`")

    check_model_module(accepts, private)
    check_model_module(returns, private)

    def wrapper(func):
        if pass_app:
            # Pass the application instance as parameter to the method
            func._pass_app = {
                'message_id': False,
                'require': pass_app_require,
                'rest': pass_app_rest,
            }
        if pass_thread_local_storage:
            func._pass_thread_local_storage = True

        if skip_args is not None:
            func._skip_arg = skip_args

        args_index = calculate_args_index(func, audit_callback)

        if asyncio.iscoroutinefunction(func):
            if pass_thread_local_storage:
                raise ValueError('pass_thread_local_storage invalid for coroutines')

            @functools.wraps(func)
            async def wrapped(*args):
                args = list(args[:args_index]) + accept_params(accepts, args[args_index:])

                result = await func(*args)

                return result
        else:
            @functools.wraps(func)
            def wrapped(*args):
                args = list(args[:args_index]) + accept_params(accepts, args[args_index:])

                result = func(*args)

                return result

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
            wrapped._no_authz_required = True

        elif not authentication_required:
            wrapped._no_auth_required = True

        elif func.__name__ not in CONFIG_CRUD_METHODS and not func.__name__.endswith('choices'):
            # All public methods should have a roles definition. This is a rough check to help developers not write
            # methods that are only accesssible to full_admin. We don't bother checking CONFIG and CRUD methods
            # and choices because they may have implicit roles through the role_prefix configuration.
            raise ValueError(f'{func.__name__}: Role definition is required for public API endpoints')

        wrapped.audit = audit
        wrapped.audit_callback = audit_callback
        wrapped.audit_extended = audit_extended
        wrapped.rate_limit = rate_limit
        wrapped.roles = roles or []
        wrapped._private = private
        wrapped._cli_private = cli_private
        if removed_in is not None:
            if not MAJOR_VERSION.match(removed_in):
                raise ValueError(
                    f'{func.__name__}: removed_in must be a valid major TrueNAS version number in the format vXX.YY'
                )

            wrapped._removed_in = removed_in

        wrapped.new_style_accepts = accepts
        wrapped.new_style_returns = returns

        return wrapped

    return wrapper


def check_model_module(model: type[BaseModel], private: bool):
    module_name = model.__module__

    if module_name in ["middlewared.plugins.test.rest", "middlewared.service.crud_service"]:
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
