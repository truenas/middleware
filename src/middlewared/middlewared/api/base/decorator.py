import asyncio
import functools
from typing import Callable

from .handler.accept import accept_params
from ..base.model import BaseModel
from middlewared.schema.processor import calculate_args_index

__all__ = ["api_method"]


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
    authentication_required: bool = True,
    authorization_required: bool = True,
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

    `authentication_required` is False when API endpoint does not require authentication. This should generally
    *not* be set and requires appropriate review and approval to validate that its use complies with security
    standards. This is incompatible with `roles`.

    `authorization_required` is False API endpoint does not require authorization, but does require authentication.
    This is incompatible with `roles`. Additional review will be required in order to validate that its use complies
    with security standards.
    """
    if list(returns.model_fields.keys()) != ["result"]:
        raise TypeError("`returns` model must only have one field called `result`")

    def wrapper(func):
        args_index = calculate_args_index(func, audit_callback)

        if asyncio.iscoroutinefunction(func):
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

        if roles:
            if not authorization_required or not authentication_required:
                raise ValueError('Authentication and authorization must be enabled in order to use roles.')
        elif not authentication_required and not authorization_required:
            # Although this is technically valid the concern is that dev has fat-fingered something
            raise ValueError('Either authentication or authorization may be disabled, but not both simultaneously.')
        elif not authentication_required:
            wrapped._no_auth_required = True
        elif not authorization_required:
            wrapped._no_authz_required = True

        wrapped.audit = audit
        wrapped.audit_callback = audit_callback
        wrapped.audit_extended = audit_extended
        wrapped.rate_limit = rate_limit
        wrapped.roles = roles or []
        wrapped._private = private

        # FIXME: This is only here for backwards compatibility and should be removed eventually
        wrapped.accepts = []
        wrapped.returns = []
        wrapped.new_style_accepts = accepts
        wrapped.new_style_returns = returns

        return wrapped

    return wrapper
