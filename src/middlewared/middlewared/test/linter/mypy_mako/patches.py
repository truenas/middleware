"""Source patches applied to a Mako-compiled module before it is type-checked.

Mako compiles each template into a Python module, but the generated source is
not mypy-clean under ``--strict``: the ``middleware`` context variable is typed
as ``Any`` (so the typesafe service accesses are never checked) and Mako's own
scaffolding lines are untyped. Each patcher here rewrites the exact lines
responsible, so the module type-checks honestly -- no error code is suppressed
and no ``# type: ignore`` is added. Genuine errors in the template's embedded
Python are left untouched.
"""

import ast
import builtins
from collections.abc import Callable
import re

# Mako emits `middleware = context.get('middleware', UNDEFINED)` (typed as Any)
# for any template that references `middleware`. Annotate it as the real
# Middleware so the typesafe service accesses are actually checked.
MIDDLEWARE_LINE = "        middleware = context.get('middleware', UNDEFINED)"
MIDDLEWARE_LINE_TYPED = "        middleware: Middleware = context.get('middleware', UNDEFINED)"
MIDDLEWARE_IMPORT = "from middlewared.main import Middleware"

# Mako always emits these scaffolding lines untyped, which trips ``--strict`` with
# errors that have nothing to do with the template's embedded logic. Annotate the
# exact lines so they type-check cleanly (``runtime`` is imported by Mako's own
# generated header; ``Any`` is injected by ``annotate_scaffolding``).
SCAFFOLDING_TYPED = {
    "def render_body(context,**pageargs):": "def render_body(context: runtime.Context, **pageargs: Any) -> str:",
    "_exports = []": "_exports: list[str] = []",
}
TYPING_IMPORT = "from typing import Any"

# Mako's own generated header; we splice our imports onto it instead of inserting
# new lines so that the compiled module keeps its original line numbering and
# Mako's embedded line map still translates mypy errors back to the .mako source.
MAKO_IMPORT_PREFIX = "from mako import runtime, filters, cache"

# For every bare name a template references, Mako emits `<name> = context.get(
# '<name>', UNDEFINED)` at the top of the render function. Mako's Context.get
# falls back to ``builtins.__dict__`` at runtime, so when the name is a builtin
# (``list``, ``str``, ``dict``, ``sorted``, ...) that line is a no-op that merely
# rebinds the builtin to itself -- but it types the name as Any, so a natural
# annotation like ``list[str]`` is rejected with "Variable 'list' is not valid as
# a type". Blank those lines (the name then resolves to the real builtin, exactly
# as it does at runtime) so template authors can annotate with plain builtins.
BUILTIN_SHADOW = re.compile(
    r"^[ \t]*(?P<name>\w+) = context\.get\('(?P=name)', UNDEFINED\)$",
    re.MULTILINE,
)


def _add_import(code: str, statement: str) -> str:
    """Append an import onto Mako's header line, preserving the line count."""
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(MAKO_IMPORT_PREFIX):
            lines[i] = f"{line}; {statement}"
            break
    else:
        # Mako's header changed shape; fall back to a (line-shifting) insert.
        lines.insert(1, statement)
    return "\n".join(lines) + "\n"


def annotate_middleware(code: str) -> str:
    """Type the ``middleware`` context variable as ``Middleware``."""
    if MIDDLEWARE_LINE not in code:
        return code
    code = code.replace(MIDDLEWARE_LINE, MIDDLEWARE_LINE_TYPED)
    return _add_import(code, MIDDLEWARE_IMPORT)


def annotate_scaffolding(code: str) -> str:
    """Annotate Mako's untyped scaffolding lines (``render_body``, ``_exports``)."""
    lines = code.splitlines()
    changed = False
    for i, line in enumerate(lines):
        replacement = SCAFFOLDING_TYPED.get(line)
        if replacement is not None:
            lines[i] = replacement
            changed = True
    code = "\n".join(lines) + "\n"
    if changed:
        code = _add_import(code, TYPING_IMPORT)
    return code


def deshadow_builtins(code: str) -> str:
    """Blank Mako's ``<builtin> = context.get('<builtin>', UNDEFINED)`` no-ops.

    See :data:`BUILTIN_SHADOW`. The substitution keeps the line (the trailing
    newline is outside the match), so Mako's line map still lines up.
    """
    def blank(match: re.Match[str]) -> str:
        return "" if hasattr(builtins, match.group("name")) else match.group(0)

    return BUILTIN_SHADOW.sub(blank, code)


# Mako compiles each `<%def name="foo(...)">` into two functions: a module-level
# `def render_foo(context, <args>):` and, inside `render_body`, a nested wrapper
# `def foo(<args>): return render_foo(context._locals(...), <args>)` that the
# `${foo()}` call sites invoke. Both return the rendered string, but Mako strips any
# annotation from the `<%def>` signature, so the template author cannot type them and
# under `--strict` they trip `no-untyped-def`/`no-untyped-call`. Every render function
# returns `str`; `context` is always a `runtime.Context`; user args can be typed only
# when their default is a literal we can read (`indent=8` -> `int`). If any user arg
# can't be typed we leave the whole def untouched rather than emit a partial signature.
MODULE_RENDER_DEF = re.compile(r"^def (?P<name>render_\w+)\((?P<params>.*)\):$", re.MULTILINE)
NESTED_RENDER_DEF = re.compile(
    r"^(?P<indent>[ \t]+)def (?P<name>\w+)\((?P<params>.*)\):"
    r"(?P<body>\n(?P=indent)    return render_(?P=name)\()",
    re.MULTILINE,
)
_LITERAL_TYPES = (bool, int, float, str, bytes)  # bool before int: isinstance(True, int)


def _literal_type_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant):
        for tp in _LITERAL_TYPES:
            if isinstance(node.value, tp):
                return tp.__name__
    return None


def _annotate_params(params: str) -> str | None:
    """Return ``params`` with a type on every arg, or None if any arg can't be typed."""
    try:
        func = ast.parse(f"def _f({params}): ...").body[0]
    except SyntaxError:
        return None
    assert isinstance(func, ast.FunctionDef)
    args = func.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
        return None  # unexpected shape

    offset = len(args.args) - len(args.defaults)
    annotated = []
    for i, arg in enumerate(args.args):
        if arg.arg == "context":
            annotated.append("context: runtime.Context")
            continue
        if i < offset:
            return None  # positional arg with no default -> type unknowable
        default = args.defaults[i - offset]
        type_name = _literal_type_name(default)
        if type_name is None:
            return None
        annotated.append(f"{arg.arg}: {type_name} = {ast.unparse(default)}")
    return ", ".join(annotated)


def annotate_render_defs(code: str) -> str:
    """Annotate Mako's ``<%def>`` render functions and their nested call wrappers."""
    def module_def(match: re.Match[str]) -> str:
        if match["name"] == "render_body":  # handled by annotate_scaffolding
            return match.group(0)
        params = _annotate_params(match["params"])
        return match.group(0) if params is None else f"def {match['name']}({params}) -> str:"

    def nested_def(match: re.Match[str]) -> str:
        params = _annotate_params(match["params"])
        if params is None:
            return match.group(0)
        return f"{match['indent']}def {match['name']}({params}) -> str:{match['body']}"

    code = MODULE_RENDER_DEF.sub(module_def, code)
    return NESTED_RENDER_DEF.sub(nested_def, code)


def annotate_locals_key(code: str) -> str:
    """Give Mako's ``__M_key`` bookkeeping comprehension a concrete element type.

    Mako copies a block's locals with
    ``... for __M_key in [<names>] if __M_key in __M_locals_builtin_stored``.
    When the block exports no locals the literal is empty (``for __M_key in []``),
    which leaves ``__M_key`` untyped under ``--strict``. The keys are always local
    variable names, so type the iterable as ``list[str]``.

    We spell it ``builtins.str`` rather than ``str``: a template may use a bare
    ``str`` that Mako pulls from the context (``str = context.get('str', ...)``),
    shadowing the builtin so a plain ``str`` would be read as that variable.
    """
    code, count = re.subn(r"for __M_key in (\[[^\]]*\])", r"for __M_key in list[builtins.str](\1)", code)
    if count:
        code = _add_import(code, "import builtins")
    return code


# Applied in order; each takes the generated source and returns a modified copy.
PATCHERS: list[Callable[[str], str]] = [
    annotate_middleware,
    annotate_scaffolding,
    annotate_render_defs,
    deshadow_builtins,
    annotate_locals_key,
]


def patch(code: str) -> str:
    """Apply every compiled-code patcher to the Mako-generated source."""
    for patcher in PATCHERS:
        code = patcher(code)
    return code
