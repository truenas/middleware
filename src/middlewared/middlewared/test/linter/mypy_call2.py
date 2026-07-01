"""mypy plugin: give ``call2`` / ``call_sync2`` the signature of their callee.

``call2(f, *args, **options)`` runs ``f(*args)`` through the middleware and returns
its result. This cannot be expressed with ordinary type hints:

* A ParamSpec forwarder (``*args: P.args, **kwargs: P.kwargs``) cannot also declare
  its own keyword options (``app``, ``pipes`` ...) -- nothing may appear between
  ``P.args`` and ``P.kwargs``.
* An overloaded callee (e.g. ``query``) passed *by reference* collapses to its first
  overload, so ``call2(svc.query, ...)`` mis-infers ``int`` instead of ``list[...]``.

So instead of static overloads, this plugin rewrites each call site's signature to
the callee's own signature: it grafts the callee's parameters onto ``call2`` and
appends the options as optional keyword arguments. mypy then resolves overloaded
callees against the *actual* arguments and accepts the options on any callee.
"""

from __future__ import annotations

from typing import Callable

from mypy.nodes import ARG_NAMED, ARG_NAMED_OPT, ARG_POS
from mypy.plugin import MethodSigContext, Plugin
from mypy.types import (
    AnyType,
    CallableType,
    FunctionLike,
    Instance,
    Overloaded,
    ProperType,
    Type,
    TypeOfAny,
    get_proper_type,
)

# Methods this plugin rewrites (matched by unqualified name; both are unique to the
# middleware call API, defined on ``CallMixin`` and ``Middleware``).
_METHODS = {"call2", "call_sync2"}

_APP_FULLNAME = "middlewared.api.base.server.app.App"
# Return types that ``call2`` unwraps: ``async def`` methods referenced as values have
# a ``Coroutine[Any, Any, R]`` return; ``call2`` yields ``R``.
_AWAITABLE_FULLNAMES = ("typing.Coroutine", "typing.Awaitable", "typing.AsyncGenerator")


class _Call2Plugin(Plugin):
    def get_method_signature_hook(
        self, fullname: str
    ) -> Callable[[MethodSigContext], FunctionLike] | None:
        name = fullname.rsplit(".", 1)[-1]
        if name not in _METHODS:
            return None
        # ``call2`` is ``async`` (awaited by the caller); ``call_sync2`` is not.
        is_async = name == "call2"
        return lambda ctx: _rewrite(ctx, is_async)


def _rewrite(ctx: MethodSigContext, is_async: bool) -> FunctionLike:
    default = ctx.default_signature
    if not isinstance(default, CallableType):
        return default
    # The first positional argument is the callee being forwarded.
    if not ctx.args or not ctx.args[0]:
        return default
    callee = get_proper_type(ctx.api.get_expression_type(ctx.args[0][0]))
    return _from_callee(callee, default, ctx, is_async) or default


def _from_callee(
    callee: ProperType, default: CallableType, ctx: MethodSigContext, is_async: bool
) -> FunctionLike | None:
    if isinstance(callee, CallableType):
        return _graft(callee, default, ctx, is_async)
    if isinstance(callee, Overloaded):
        grafted = [_graft(item, default, ctx, is_async) for item in callee.items]
        if grafted and all(g is not None for g in grafted):
            return Overloaded([g for g in grafted if g is not None])
    return None


def _graft(
    callee: CallableType, default: CallableType, ctx: MethodSigContext, is_async: bool
) -> CallableType | None:
    # Strip a leading ``App`` parameter -- ``pass_app`` methods receive it via injection,
    # not from the caller (mirrors the ``Concatenate[App, P]`` handling in the overloads).
    start = 1 if callee.arg_types and _is_app(callee.arg_types[0]) else 0
    inner_types = list(callee.arg_types[start:])
    inner_kinds = list(callee.arg_kinds[start:])
    inner_names = list(callee.arg_names[start:])

    # The call-machinery options are the keyword-only parameters declared on ``call2`` itself
    # (``app``, ``pipes`` ...). Lifting them from the implementation signature keeps their real
    # types -- and keeps ``call2`` and ``call_sync2`` (whose option sets differ) each correct.
    opt_types: list[Type] = []
    opt_kinds = []
    opt_names = []
    for arg_type, arg_kind, arg_name in zip(default.arg_types, default.arg_kinds, default.arg_names):
        if arg_kind in (ARG_NAMED, ARG_NAMED_OPT):
            opt_types.append(arg_type)
            opt_kinds.append(ARG_NAMED_OPT)  # always optional at the call site
            opt_names.append(arg_name)

    any_type = AnyType(TypeOfAny.special_form)
    # The value the caller ultimately gets: an ``async def`` referenced as a value returns
    # ``Coroutine[Any, Any, R]``, so ``call2`` yields ``R``.
    result = _awaited(callee.ret_type)
    # ``call2`` is itself ``async``, so its *signature* return must be the awaitable that the
    # caller ``await``s; ``call_sync2`` returns the value directly.
    ret_type: Type = ctx.api.named_generic_type("typing.Coroutine", [any_type, any_type, result]) \
        if is_async else result

    return default.copy_modified(
        # ``f`` itself is untyped here (``Any``) -- it is only a placeholder; the callee's
        # real parameters follow it so the call's remaining arguments are type-checked.
        arg_types=[any_type, *inner_types, *opt_types],
        arg_kinds=[ARG_POS, *inner_kinds, *opt_kinds],
        arg_names=[None, *inner_names, *opt_names],
        ret_type=ret_type,
        variables=list(callee.variables),
    )


def _is_app(t: Type) -> bool:
    proper = get_proper_type(t)
    return isinstance(proper, Instance) and proper.type.fullname == _APP_FULLNAME


def _awaited(ret: Type) -> Type:
    """The value an ``async def`` produces once awaited: ``Coroutine[Any, Any, R]`` -> ``R``."""
    proper = get_proper_type(ret)
    if isinstance(proper, Instance) and proper.type.fullname in _AWAITABLE_FULLNAMES and proper.args:
        return proper.args[-1]
    return ret


def plugin(version: str) -> type[Plugin]:
    return _Call2Plugin
