"""mypy plugin: re-narrow ``QueryOptions(get=True)`` / ``QueryOptions(count=True)``
to the ``QueryOptionsGet`` / ``QueryOptionsCount`` subclasses.

This narrowing is what lets ``query()`` overloads resolve a ``get=True`` call to a
single ``Entry`` (and a ``count=True`` call to ``int``) instead of ``list[Entry]``.
"""

from typing import Callable

from mypy.nodes import TypeInfo
from mypy.plugin import FunctionContext, Plugin
from mypy.types import Instance, LiteralType, Type, get_proper_type

_SUFFIX = ".common.QueryOptions"


def _is_literal_true(ctx: FunctionContext, name: str) -> bool:
    """Return True only when ``name`` was passed as a literal ``True`` at the call site."""
    for names, types in zip(ctx.arg_names, ctx.arg_types):
        for arg_name, arg_type in zip(names, types):
            if arg_name != name:
                continue
            proper = get_proper_type(arg_type)
            literal = proper.last_known_value if isinstance(proper, Instance) else proper
            if isinstance(literal, LiteralType) and literal.value is True:
                return True
    return False


class _QueryOptionsPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname.endswith(_SUFFIX):
            return self._narrow
        return None

    def _sibling(self, default: Type, name: str) -> Type | None:
        """Resolve a sibling class (e.g. ``QueryOptionsGet``) in the same module."""
        if not isinstance(default, Instance):
            return None
        module = default.type.fullname.rsplit(".", 1)[0]
        sym = self.lookup_fully_qualified(f"{module}.{name}")
        if sym is not None and isinstance(sym.node, TypeInfo):
            return Instance(sym.node, [])
        return None

    def _narrow(self, ctx: FunctionContext) -> Type:
        default = ctx.default_return_type
        if _is_literal_true(ctx, "get"):
            return self._sibling(default, "QueryOptionsGet") or default
        if _is_literal_true(ctx, "count"):
            return self._sibling(default, "QueryOptionsCount") or default
        return default


def plugin(version: str) -> type[Plugin]:
    return _QueryOptionsPlugin
