"""Check what the etc_files renderers hide from the rest of the build.

``EtcService`` renders a config file one of two ways: a Mako template, or a
Python script exposing ``render()``. Instantiating the service compiles every
template and imports every script, so the ``--dump-methods`` build step already
fails on a template that does not compile, and on a script that does not
import.

Two things survive that step, because neither runs until a system needs the
config file:

- The imports in a template's body. Mako compiles the body into a render
  function, so importing the template never executes them. They are resolved
  here from the compiled module's AST.
- The ``render()`` a script must expose. ``PyRenderer`` only looks it up when
  it renders, so a script missing it imports cleanly.

Usage::

    python -m middlewared.test.linter.etc_check [TARGET ...]

A ``TARGET`` is a ``.mako`` file, a ``.py`` file, or a directory searched
recursively. Without targets the whole ``etc_files`` tree is checked.

An import inside a ``try`` that catches ``ImportError`` is skipped. The
template already handles the absence of that module.
"""

import ast
import importlib
import os
import sys

from mako.lookup import TemplateLookup
from mako.template import ModuleInfo

import middlewared

LOOKUP_BASE = os.path.dirname(os.path.abspath(middlewared.__file__))
DEFAULT_TARGET = os.path.join(LOOKUP_BASE, "etc_files")

# The runtime lookup in middlewared.utils.mako caches compiled modules under
# /run/mako. A build must not write there, and a stale entry would hide a
# template that no longer compiles, so compile in memory instead.
lookup = TemplateLookup(directories=[LOOKUP_BASE])

# An import under one of these handlers is optional by design.
OPTIONAL_UNDER = frozenset({"ImportError", "ModuleNotFoundError", "Exception", "BaseException"})

RESET, BOLD, RED = "\x1b[0m", "\x1b[1m", "\x1b[91m"

Problem = tuple[str, str]


def collect_renderers(targets: list[str]) -> list[str]:
    """Expand the targets into a sorted, de-duplicated list of renderer files."""
    files: set[str] = set()
    for target in targets:
        if os.path.isdir(target):
            for root, dirs, names in os.walk(target):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for name in names:
                    if name.endswith((".mako", ".py")):
                        files.add(os.path.abspath(os.path.join(root, name)))
        elif target.endswith((".mako", ".py")):
            files.add(os.path.abspath(target))
        else:
            raise SystemExit(f"error: not a renderer file or directory: {target}")

    return sorted(files)


def _handler_catches_import_error(node: ast.Try | ast.TryStar) -> bool:
    for handler in node.handlers:
        if handler.type is None:
            return True

        for sub in ast.walk(handler.type):
            if isinstance(sub, ast.Name) and sub.id in OPTIONAL_UNDER:
                return True
            if isinstance(sub, ast.Attribute) and sub.attr in OPTIONAL_UNDER:
                return True

    return False


def iter_imports(node: ast.AST, guarded: bool = False) -> list[ast.Import | ast.ImportFrom]:
    """Return every import statement that the module runs unguarded.

    Mako wraps ``render_body`` in ``try``/``finally``, so guarding is decided
    per handler, not by the presence of a ``try``.
    """
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        if guarded:
            return []

        return [node]

    found: list[ast.Import | ast.ImportFrom] = []
    if isinstance(node, (ast.Try, ast.TryStar)):
        body_guarded = guarded or _handler_catches_import_error(node)
        for statement in node.body:
            found.extend(iter_imports(statement, body_guarded))

        for rest in (*node.handlers, *node.orelse, *node.finalbody):
            found.extend(iter_imports(rest, guarded))

        return found

    for child in ast.iter_child_nodes(node):
        found.extend(iter_imports(child, guarded))

    return found


def resolve_import(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Return one message per name the import statement cannot resolve."""
    if isinstance(node, ast.Import):
        problems = []
        for alias in node.names:
            try:
                importlib.import_module(alias.name)
            except Exception as exc:
                problems.append(f"import {alias.name}: {type(exc).__name__}: {exc}")

        return problems

    # A relative import has no package to resolve against once Mako compiles
    # the template into a standalone module.
    if node.level or node.module is None:
        return []

    try:
        module = importlib.import_module(node.module)
    except Exception as exc:
        return [f"from {node.module} import ...: {type(exc).__name__}: {exc}"]

    problems = []
    for alias in node.names:
        if alias.name == "*" or hasattr(module, alias.name):
            continue

        try:
            importlib.import_module(f"{node.module}.{alias.name}")
        except Exception:
            problems.append(f"cannot import name {alias.name!r} from {node.module!r}")

    return problems


def check_template(path: str) -> list[Problem]:
    """Compile a Mako template and resolve every import its body makes."""
    rel = os.path.relpath(path, LOOKUP_BASE)
    try:
        source = lookup.get_template(rel).code
    except Exception as exc:
        return [(rel, f"does not compile: {type(exc).__name__}: {exc}")]

    line_map = ModuleInfo.get_module_source_metadata(source, full_line_map=True)["full_line_map"]
    problems = []
    for node in iter_imports(ast.parse(source)):
        mako_line = 0
        if node.lineno <= len(line_map):
            mako_line = line_map[node.lineno - 1]

        for problem in resolve_import(node):
            problems.append((f"{rel}:{mako_line or '?'}", problem))

    return problems


def binds_render(tree: ast.Module) -> bool:
    """Whether the module's top level binds the name PyRenderer calls."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "render":
            return True

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "render":
                    return True

        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "render":
                return True

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name) == "render":
                    return True

    return False


def check_script(path: str) -> list[Problem]:
    """Check that a Python renderer exposes the render() PyRenderer calls.

    The --dump-methods build step already imports every script, so anything
    that surfaces on import is covered before this runs.
    """
    rel = os.path.relpath(path, LOOKUP_BASE)
    with open(path, "rb") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [(f"{rel}:{exc.lineno or '?'}", f"{type(exc).__name__}: {exc.msg}")]

    if not binds_render(tree):
        return [(rel, "renderer defines no render()")]

    return []


def check_renderer(path: str) -> list[Problem]:
    if path.endswith(".mako"):
        return check_template(path)

    return check_script(path)


def main(argv: list[str]) -> int:
    targets = argv
    if not targets:
        targets = [DEFAULT_TARGET]

    renderers = collect_renderers(targets)
    if not renderers:
        raise SystemExit("error: no renderer files found in the given targets")

    color = sys.stdout.isatty()
    problems = []
    for path in renderers:
        problems.extend(check_renderer(path))

    for location, detail in problems:
        if color:
            print(f"{BOLD}{location}{RESET}: {RED}error{RESET}: {detail}")
        else:
            print(f"{location}: error: {detail}")

    templates = sum(1 for path in renderers if path.endswith(".mako"))
    summary = f"{templates} template(s) and {len(renderers) - templates} script(s)"
    if problems:
        print(f"\nFound {len(problems)} problem(s) in {summary}")
        return 1

    print(f"Checked {summary}: no problems found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
