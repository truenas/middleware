"""Type-check the Python embedded in Mako templates.

Mako compiles each template into a Python module. Templates that use the
typesafe pattern (``middleware.call_sync2(middleware.services.kmip.config)``
etc.) are worth running mypy against, but the compiled module is not mypy-clean
out of the box -- see :mod:`.patches` for the source rewrites that fix that
(notably typing ``middleware`` as :class:`middlewared.main.Middleware`) before
the module is handed to mypy.

Usage::

    python -m middlewared.test.linter.mypy_mako [TARGET ...] [MYPY_ARG ...]

A ``TARGET`` is any argument that exists on disk: either a ``.mako`` file or a
directory (searched recursively for ``*.mako``). Every other argument is
forwarded to mypy verbatim, so the CI flags work unchanged::

    python -m middlewared.test.linter.mypy_mako \\
        middlewared/etc_files/pykmip --follow-imports silent --strict

Use ``--`` to stop target detection and force the remaining arguments to mypy
(useful when a mypy flag value happens to be an existing path)::

    python -m middlewared.test.linter.mypy_mako middlewared/etc_files/pykmip \\
        -- --config-file mypy.ini
"""

import dataclasses
import os
import re
import subprocess
import sys
import tempfile

from mako.template import ModuleInfo

import middlewared
from middlewared.utils.mako import get_template

from . import patches

# The Mako TemplateLookup is rooted at the middlewared package directory and
# templates are addressed by a URI relative to it. mypy runs from its parent
# (src/middlewared) so that ``import middlewared`` resolves, matching CI.
LOOKUP_BASE = os.path.dirname(os.path.abspath(middlewared.__file__))
SRC_MIDDLEWARED = os.path.dirname(LOOKUP_BASE)

# Strips ANSI so we can parse mypy output regardless of its own colorization.
ANSI = re.compile(r"\x1b\[[0-9;]*m")
# `<path>:<line>:<col>: <severity>: <message>` (we force --show-column-numbers).
MYPY_LINE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+):\s(?P<rest>.*)$")

# Compiled-context window shown around each error.
CONTEXT = 5

RESET, BOLD, DIM = "\x1b[0m", "\x1b[1m", "\x1b[2m"
SEVERITY_COLOR = {"error": "\x1b[91m", "warning": "\x1b[93m", "note": "\x1b[96m"}
CARET_COLOR = "\x1b[91m"


@dataclasses.dataclass
class Compiled:
    """A compiled template and the data needed to map mypy errors back to it."""

    mako_rel: str  # template path relative to LOOKUP_BASE (e.g. etc_files/...)
    source: list[str]  # compiled module lines, for showing context
    line_map: list[int]  # full_line_map: compiled line (1-based) -> .mako line


def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    """Partition argv into Mako targets (existing paths) and mypy arguments.

    Everything after a literal ``--`` is forced into the mypy bucket.
    """
    targets: list[str] = []
    mypy_args: list[str] = []
    forward_rest = False
    for arg in argv:
        if forward_rest:
            mypy_args.append(arg)
        elif arg == "--":
            forward_rest = True
        elif os.path.exists(arg):
            targets.append(arg)
        else:
            mypy_args.append(arg)
    return targets, mypy_args


def collect_mako_files(targets: list[str]) -> list[str]:
    """Expand the targets into a sorted, de-duplicated list of .mako files."""
    files: set[str] = set()
    for target in targets:
        if os.path.isdir(target):
            for root, _, names in os.walk(target):
                for name in names:
                    if name.endswith(".mako"):
                        files.add(os.path.abspath(os.path.join(root, name)))
        elif target.endswith(".mako"):
            files.add(os.path.abspath(target))
        else:
            raise SystemExit(f"error: not a .mako file or directory: {target}")
    return sorted(files)


def compile_mako(path: str) -> str:
    """Compile a single .mako file to patched, type-checkable Python source."""
    if os.path.commonpath([path, LOOKUP_BASE]) != LOOKUP_BASE:
        raise SystemExit(
            f"error: {path} is not under the middlewared package ({LOOKUP_BASE}); "
            f"the Mako template lookup cannot address it."
        )
    uri = os.path.relpath(path, LOOKUP_BASE)
    return patches.patch(get_template(uri).code)


def _color(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{RESET}" if enabled and code else text


def _render(stdout: str, compiled: dict[str, Compiled], color: bool) -> None:
    """Rewrite mypy output to point at the .mako source and show compiled context."""
    for raw in stdout.splitlines():
        match = MYPY_LINE.match(ANSI.sub("", raw))
        info = compiled.get(match["path"]) if match else None
        if match is None or info is None:
            print(raw)  # summaries and anything not tied to a compiled file
            continue

        compiled_ln, col = int(match["line"]), int(match["col"])
        rest = match["rest"]
        severity = rest.split(":", 1)[0]
        mako_ln = info.line_map[compiled_ln - 1] if compiled_ln <= len(info.line_map) else 0

        location = _color(f"{info.mako_rel}:{mako_ln or '?'}", BOLD, color)
        sev = _color(severity, SEVERITY_COLOR.get(severity, ""), color)
        print(f"{location}: {sev}:{rest[len(severity) + 1 :]}")

        if severity == "error":
            _print_context(info.source, compiled_ln, col, color)


def _print_context(source: list[str], error_ln: int, col: int, color: bool) -> None:
    """Show the compiled file around ``error_ln`` with a caret under the column."""
    lo, hi = max(1, error_ln - CONTEXT), min(len(source), error_ln + CONTEXT)
    width = len(str(hi))
    for n in range(lo, hi + 1):
        gutter = f"{n:>{width}} | "
        is_error = n == error_ln
        print(f"  {_color(gutter, BOLD if is_error else DIM, color)}{source[n - 1]}")
        if is_error:
            print(_color(" " * (2 + len(gutter) + col - 1) + "^", CARET_COLOR, color))


def main(argv: list[str]) -> int:
    targets, mypy_args = split_args(argv)
    if not targets:
        print(__doc__, file=sys.stderr)
        raise SystemExit("error: no .mako files or directories specified")

    mako_files = collect_mako_files(targets)
    if not mako_files:
        raise SystemExit("error: no .mako files found in the given targets")

    with tempfile.TemporaryDirectory(prefix="mypy_mako_") as tmpdir:
        compiled: dict[str, Compiled] = {}
        for path in mako_files:
            rel = os.path.relpath(path, LOOKUP_BASE)
            source = compile_mako(path)
            # Flatten the package-relative path into a readable temp filename.
            out = os.path.join(tmpdir, rel.replace(os.sep, "__") + ".py")
            with open(out, "w") as f:
                f.write(source)
            meta = ModuleInfo.get_module_source_metadata(source, full_line_map=True)
            compiled[out] = Compiled(rel, source.splitlines(), meta["full_line_map"])

        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--show-column-numbers", *compiled, *mypy_args],
            cwd=SRC_MIDDLEWARED,
            capture_output=True,
            text=True,
        )

    if result.stderr:
        sys.stderr.write(result.stderr)
    _render(result.stdout, compiled, color=sys.stdout.isatty())
    return result.returncode
