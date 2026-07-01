"""Source patches applied to a Mako-compiled module before it is type-checked.

Mako compiles each template into a Python module, but the generated source is
not mypy-clean under ``--strict``: the ``middleware`` context variable is typed
as ``Any`` (so the typesafe service accesses are never checked) and Mako's own
scaffolding lines are untyped. Each patcher here rewrites the exact lines
responsible, so the module type-checks honestly -- no error code is suppressed
and no ``# type: ignore`` is added. Genuine errors in the template's embedded
Python are left untouched.
"""

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
    annotate_locals_key,
]


def patch(code: str) -> str:
    """Apply every compiled-code patcher to the Mako-generated source."""
    for patcher in PATCHERS:
        code = patcher(code)
    return code
