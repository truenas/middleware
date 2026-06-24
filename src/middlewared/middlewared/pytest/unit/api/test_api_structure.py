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
# CRUD method names as exposed in the API (`do_create` is the method `<namespace>.create`, etc.).
CRUD_METHOD_NAMES = {"do_create": "create", "do_update": "update", "do_delete": "delete"}
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


def check_docstring(docstr: str | None, must_have: bool = False, allow_markdown: bool = True):
    """Enforce API docstring rules.

    1. First character cannot be a lowercase letter
    2. Last character must be a period
    3. Last character of each line must be a period or colon

    Rules 2 and 3 are applied to prose only. RST literal blocks (indented), directives (lines
    starting with ``.. ``), and list items are structural -- ``reflow_docstring`` preserves them
    verbatim -- so they are exempt (e.g. a docstring may legitimately end in a code example or a
    ``.. versionadded::`` directive).

    When ``allow_markdown`` is ``True`` (the default, used for model field descriptions), rules are
    skipped if the docstring appears to use Markdown conventions (bullet lists, bold, or em-dashes).

    """
    if not docstr:
        if must_have:
            # Either a docstring or `Field(description=...)` will do
            return "Must have description"
        return

    if allow_markdown and (
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


def _node_name(node):
    """Return the bare name of a decorator or base-class node (handles ``@x``, ``@x()`` and ``x[...]``)."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Subscript):
        node = node.value
    return getattr(node, "id", None) or getattr(node, "attr", None)


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def _config_value(class_node, key):
    """Return the literal value assigned to ``key`` in the service's nested ``Config``, else None."""
    for member in class_node.body:
        if isinstance(member, ast.ClassDef) and member.name == "Config":
            for stmt in member.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == key for t in stmt.targets)
                    and isinstance(stmt.value, ast.Constant)
                ):
                    return stmt.value.value
    return None


def _service_namespace(class_node):
    """The API namespace of a service: explicit ``Config.namespace`` or derived from the class name."""
    if (namespace := _config_value(class_node, "namespace")) is not None:
        return namespace
    name = class_node.name
    return (name.removesuffix("Service")).lower()


def _public_api_methods(class_node):
    """Yield the public-API method nodes defined directly in ``class_node``.

    A method is public when decorated with one of ``PUBLIC_API_DECORATORS`` and not made private by a
    private decorator or a ``private=True`` keyword argument to the API decorator.
    """
    for node in class_node.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorators = [_node_name(d) for d in node.decorator_list]
        if not any(name in PUBLIC_API_DECORATORS for name in decorators):
            continue
        if any(name in PRIVATE_DECORATORS for name in decorators):
            continue
        if any(
            isinstance(d, ast.Call)
            and _node_name(d) in PUBLIC_API_DECORATORS
            and any(kw.arg == "private" and _is_true(kw.value) for kw in d.keywords)
            for d in node.decorator_list
        ):
            continue
        yield node


def _collect_public_api(package_root):
    """Walk the package once and return ``(methods, universe)``.

    ``methods`` is a list of ``(location, name, reflowed_or_None)`` for every public API method
    (``name`` being its ``namespace.method`` API name, ``do_create``/etc. mapped to ``create``/etc.).
    ``universe`` is the set of every public method name, including the CRUD/config methods that base
    classes provide implicitly, so that ``:method:`` cross-references resolve when docstrings render.
    """
    methods = []
    universe = set()
    for path in sorted(package_root.rglob("*.py")):
        if "pytest" in path.relative_to(package_root).parts:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef) or _config_value(class_node, "private") is True:
                continue

            own_methods = list(_public_api_methods(class_node))
            bases = {_node_name(b) for b in class_node.bases}
            has_config = any(isinstance(m, ast.ClassDef) and m.name == "Config" for m in class_node.body)
            if not (own_methods or has_config):
                continue  # not a service

            namespace = _service_namespace(class_node)
            if any(b and b.endswith(("CRUDService", "SharingService")) for b in bases):
                universe.update(f"{namespace}.{m}" for m in ("query", "get_instance", "create", "update", "delete"))
            if any(b and b.endswith(("ConfigService", "SystemServiceService")) for b in bases):
                universe.update(f"{namespace}.{m}" for m in ("config", "update"))

            for node in own_methods:
                name = f"{namespace}.{CRUD_METHOD_NAMES.get(node.name, node.name)}"
                universe.add(name)
                docstring = ast.get_docstring(node)
                location = f"{path.relative_to(package_root)}:{node.lineno} {node.name}"
                methods.append((location, name, reflow_docstring(docstring) if docstring else None))
    return methods, universe


@pytest.fixture(scope="module")
def public_api():
    """Every public API method (and the full set of method names), collected once from the source."""
    return _collect_public_api(pathlib.Path(middlewared.__file__).parent)


def test_api_method_docstrings(public_api):
    """Every public API method must have a docstring that satisfies the API docstring rules.

    Each docstring is reflowed exactly as it is for the generated API documentation before the
    rules are applied, so hard-wrapped prose is validated as the single paragraph it renders to.
    """
    methods, _universe = public_api
    errors = [
        SyntaxWarning(f"{location}: {err}")
        for location, _name, reflowed in methods
        if (err := check_docstring(reflowed, must_have=True, allow_markdown=False))
    ]
    if errors:
        raise ExceptionGroup("Improper public API method docstring(s)", errors)


@pytest.fixture(scope="module")
def api_doc_pages(public_api, tmp_path_factory):
    """Render the API method docstrings as a Sphinx project, mirroring the generated docs.

    Each documented method becomes ``api_methods_<name>.rst`` holding its reflowed docstring; every
    other method name gets a stub page, so ``:method:`` cross-references resolve and a remaining
    ``ref.doc`` warning means a reference to a method that does not exist. Returns
    ``(srcdir, page_locations)`` mapping each content page to its source location.
    """
    methods, universe = public_api
    srcdir = tmp_path_factory.mktemp("api_method_docs")
    (srcdir / "conf.py").write_text("project = 'API'\nextensions = []\nexclude_patterns = []\n")

    page_locations = {}
    documented = set()
    for location, name, reflowed in methods:
        if reflowed is None:
            continue
        (srcdir / f"api_methods_{name}.rst").write_text(f"{name}\n{'=' * len(name)}\n\n{reflowed}\n")
        page_locations[f"api_methods_{name}.rst"] = location
        documented.add(name)

    for name in universe - documented:
        (srcdir / f"api_methods_{name}.rst").write_text(f"{name}\n{'=' * len(name)}\n")

    toctree = "".join(f"   {p.stem}\n" for p in sorted(srcdir.glob("api_methods_*.rst")))
    (srcdir / "index.rst").write_text(f"API\n===\n\n.. toctree::\n   :maxdepth: 1\n\n{toctree}")
    return srcdir, page_locations


def _locate(line, page_locations):
    """Rewrite a tool finding's ``api_methods_<name>.rst:LINE: message`` to its source location."""
    if (m := re.search(r"(api_methods_[\w.]+\.rst):\d+: (.*)", line)) and m.group(1) in page_locations:
        return f"{page_locations[m.group(1)]}: {m.group(2)}"
    return line


def test_api_method_docstrings_render(api_doc_pages, tmp_path):
    """Reflowed public API method docstrings must render as valid RST with all references resolving.

    They are built with the same Sphinx machinery used for the API documentation. Because every API
    method name has a page, a ``ref.doc`` warning means a ``:method:`` reference points at a method
    that does not exist.
    """
    srcdir, page_locations = api_doc_pages
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-b", "dummy", "-q", str(srcdir), str(tmp_path / "out")],
        capture_output=True,
        text=True,
    )

    errors = [
        SyntaxWarning(_locate(line, page_locations))
        for line in (result.stdout + result.stderr).splitlines()
        if "WARNING" in line or "ERROR" in line
    ]
    if errors:
        raise ExceptionGroup("Public API method docstring(s) with invalid RST or broken references", errors)


def test_api_method_docstrings_sphinx_lint(api_doc_pages):
    """Reflowed public API method docstrings must pass sphinx-lint.

    ``default-role`` is enabled on top of the default checks so that single-backtick literals (which
    should be double backticks) are rejected, alongside role and inline-markup mistakes -- e.g. a
    ``:method:`` reference missing its closing backtick, or unbalanced inline literals -- that render
    incorrectly without raising a parse error.
    """
    srcdir, page_locations = api_doc_pages
    result = subprocess.run(
        [sys.executable, "-m", "sphinxlint", "--enable", "default-role", str(srcdir)],
        capture_output=True,
        text=True,
    )

    errors = [
        SyntaxWarning(_locate(line, page_locations))
        for line in (result.stdout + result.stderr).splitlines()
        if re.search(r"api_methods_[\w.]+\.rst:\d+:", line)
    ]
    if errors:
        raise ExceptionGroup("Public API method docstring(s) flagged by sphinx-lint", errors)
