import ast
import importlib
import inspect
import os
import pathlib
import pkgutil
import re
import subprocess
import sys

import pytest

import middlewared
import middlewared.api
from middlewared.api.base import BaseModel
from middlewared.api.base.server.doc import reflow_docstring

PUBLIC_API_DECORATORS = frozenset({"api_method", "filterable_api_method"})
PRIVATE_DECORATORS = frozenset({"private", "private_method"})
# RST list markers, mirroring `reflow_docstring`'s definition of a structural (non-prose) block.
RST_LIST_MARKER = re.compile(r"([-*+]|[0-9]+\.|#\.) ")


@pytest.fixture(scope="module")
def current_api_package():
    # Get the API directory path
    api_dir = pathlib.Path(middlewared.api.__file__).parent

    # Find all version directories
    with os.scandir(api_dir) as sdir:
        version_dirs = [
            d.name for d in sdir
            if d.is_dir() and d.name.startswith('v')
        ]

    # Sort to get the latest version
    latest_version = sorted(version_dirs)[-1]

    # Import and return the latest API package
    module_name = f"middlewared.api.{latest_version}"
    return importlib.import_module(module_name)


def check_docstring(docstr: str | None, must_have: bool = False):
    """Enforce API docstring rules.

    Rules are skipped if the docstring contains any asterisks (*) or hyphens (-).
    1. First character cannot be a lowercase letter
    2. Last character must be a period
    3. Last character of each line must be a period or colon

    Rules 2 and 3 are applied to prose only. RST literal blocks (indented), directives (lines
    starting with ``.. ``), and list items are structural -- ``reflow_docstring`` preserves them
    verbatim -- so they are exempt (e.g. a docstring may legitimately end in a code example or a
    ``.. versionadded::`` directive).

    """
    if not docstr:
        if must_have:
            # Either a docstring or `Field(description=...)` will do
            return "Must have description"
        return

    if (
        any(line.startswith(("* ", "- ", "    {")) for line in docstr.splitlines() if line) or
        any(c in docstr for c in ["**", "--"])
    ):
        # Just assume Markdown and skip rules check
        return

    docstr = docstr.strip()
    if docstr[0].islower() and docstr.partition(" ")[0] not in {"pCloud", "iSCSI"}:
        return "Docstring cannot start with lowercase letter"

    lines = [line for line in docstr.splitlines() if line]

    def is_structural(line):
        return bool(line[:1].isspace() or line.startswith(".. ") or RST_LIST_MARKER.match(line))

    if not docstr.endswith(".") and not is_structural(lines[-1]):
        return "Docstring must end with a period"
    if any(line[-1] not in (".", ":") for line in lines if not is_structural(line)):
        return "Lines must end with a colon or a period"


def test_api_current_module_exports(current_api_package):
    assert "BaseModel" not in dir(current_api_package), "__all__ must be defined in all API model modules"


def test_api_docstrings(current_api_package):
    """Enforce API docstring syntax rules."""
    errors = []
    for importer, modname, ispkg in pkgutil.iter_modules(
        current_api_package.__path__, current_api_package.__name__ + "."
    ):
        # An API file containing models
        module = importer.find_spec(modname).loader.load_module(modname)

        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, BaseModel):
                # Check model's docstring
                if err := check_docstring(obj.__doc__):
                    errors.append(SyntaxWarning(f"{name}: {err}"))

                # Iterate over field docstrings
                for field_name, field_info in obj.model_fields.items():
                    if field_info.exclude:
                        continue
                    if err := check_docstring(field_info.description, field_name != "result"):
                        errors.append(SyntaxWarning(f"{modname}.{name}.{field_name}: {err}"))

    if errors:
        raise ExceptionGroup(f"Improper docstring(s) detected in {current_api_package.__name__}", errors)


def _decorator_name(node):
    """Return the bare name of a decorator node."""
    target = node.func if isinstance(node, ast.Call) else node
    return getattr(target, "id", None) or getattr(target, "attr", None)


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def _service_is_private(class_node):
    """Return whether a service class declares ``private = True`` in its ``Config``."""
    for member in class_node.body:
        if isinstance(member, ast.ClassDef) and member.name == "Config":
            for stmt in member.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "private" for t in stmt.targets)
                    and _is_true(stmt.value)
                ):
                    return True
    return False


def _iter_public_api_methods(tree):
    """Yield each method node in `tree` that is exposed in the public API.

    A method is public when it is decorated with one of `PUBLIC_API_DECORATORS` and is not made
    private by its enclosing service's ``Config``, a private decorator, or a ``private=True`` keyword
    argument to the API decorator.
    """
    for class_node in ast.walk(tree):
        if not isinstance(class_node, ast.ClassDef):
            continue

        service_private = _service_is_private(class_node)
        for node in class_node.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            decorator_names = [_decorator_name(d) for d in node.decorator_list]
            if not any(name in PUBLIC_API_DECORATORS for name in decorator_names):
                continue

            if service_private or any(name in PRIVATE_DECORATORS for name in decorator_names):
                continue

            if any(
                isinstance(d, ast.Call)
                and _decorator_name(d) in PUBLIC_API_DECORATORS
                and any(kw.arg == "private" and _is_true(kw.value) for kw in d.keywords)
                for d in node.decorator_list
            ):
                continue

            yield node


def test_api_method_docstrings():
    """Every public API method must have a docstring that satisfies the API docstring rules.

    Each docstring is reflowed exactly as it is for the generated API documentation before the
    rules are applied, so hard-wrapped prose is validated as the single paragraph it renders to.
    """
    package_root = pathlib.Path(middlewared.__file__).parent
    errors = []
    for path in sorted(package_root.rglob("*.py")):
        # Skip the test suite itself.
        if "pytest" in path.relative_to(package_root).parts:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _iter_public_api_methods(tree):
            docstring = ast.get_docstring(node)
            reflowed = reflow_docstring(docstring) if docstring else None
            if err := check_docstring(reflowed, must_have=True):
                rel_path = path.relative_to(package_root)
                errors.append(SyntaxWarning(f"{rel_path}:{node.lineno}: {node.name}: {err}"))

    if errors:
        raise ExceptionGroup("Improper public API method docstring(s)", errors)


@pytest.fixture(scope="module")
def reflowed_docstring_pages(tmp_path_factory):
    """Write each public API method's reflowed docstring as an isolated RST page.

    Returns ``(srcdir, pages)``, where ``pages`` maps each ``<name>.rst`` file to the
    ``path:line method`` it came from, so tool output can be translated back to the source.
    """
    srcdir = tmp_path_factory.mktemp("api_method_docstrings")
    (srcdir / "conf.py").write_text("project = 'API'\nextensions = []\nexclude_patterns = []\n")

    pages = {}
    names = []
    package_root = pathlib.Path(middlewared.__file__).parent
    for path in sorted(package_root.rglob("*.py")):
        if "pytest" in path.relative_to(package_root).parts:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _iter_public_api_methods(tree):
            docstring = ast.get_docstring(node)
            if not docstring:
                continue

            name = f"m{len(names):04d}"
            # A neutral title avoids RST parsing a source path (e.g. ``account_``) as a reference.
            title = f"Method {len(names)}"
            page = f"{title}\n{'=' * len(title)}\n\n{reflow_docstring(docstring)}\n"
            (srcdir / f"{name}.rst").write_text(page)
            pages[f"{name}.rst"] = f"{path.relative_to(package_root)}:{node.lineno} {node.name}"
            names.append(name)

    toctree = "".join(f"   {name}\n" for name in names)
    (srcdir / "index.rst").write_text(f"API\n===\n\n.. toctree::\n   :maxdepth: 1\n\n{toctree}")
    return srcdir, pages


def _locate(line, pages):
    """Rewrite a ``<tmp>/mNNNN.rst:LINE: message`` tool finding to ``source location: message``."""
    if m := re.search(r"(m\d{4}\.rst):\d+: (.*)", line):
        if m.group(1) in pages:
            return f"{pages[m.group(1)]}: {m.group(2)}"
    return line


def test_api_method_docstrings_render(reflowed_docstring_pages, tmp_path):
    """Reflowed public API method docstrings must be structurally valid RST.

    They are parsed with the same Sphinx machinery used to build the API documentation. Cross-
    reference resolution warnings (``ref.doc``) are ignored because each method page is built in
    isolation, so the ``:doc:`` targets expanded from ``:method:`` do not resolve here.
    """
    pytest.importorskip("sphinx")
    srcdir, pages = reflowed_docstring_pages
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "dummy", "-q", str(srcdir), str(tmp_path / "out")],
        capture_output=True,
        text=True,
    )

    errors = [
        SyntaxWarning(_locate(line, pages))
        for line in (result.stdout + result.stderr).splitlines()
        if ("WARNING" in line or "ERROR" in line) and "[ref.doc]" not in line
    ]
    if errors:
        raise ExceptionGroup("Public API method docstring(s) with invalid RST", errors)


def test_api_method_docstrings_sphinx_lint(reflowed_docstring_pages):
    """Reflowed public API method docstrings must pass sphinx-lint.

    ``default-role`` is enabled on top of the default checks so that single-backtick literals (which
    should be double backticks) are rejected, alongside role and inline-markup mistakes -- e.g. a
    ``:method:`` reference missing its closing backtick, or unbalanced inline literals -- that render
    incorrectly without raising a parse error.
    """
    pytest.importorskip("sphinxlint")
    srcdir, pages = reflowed_docstring_pages
    result = subprocess.run(
        [sys.executable, "-m", "sphinxlint", "--enable", "default-role", str(srcdir)],
        capture_output=True,
        text=True,
    )

    errors = [
        SyntaxWarning(_locate(line, pages))
        for line in (result.stdout + result.stderr).splitlines()
        if re.search(r"m\d{4}\.rst:\d+:", line)
    ]
    if errors:
        raise ExceptionGroup("Public API method docstring(s) flagged by sphinx-lint", errors)
