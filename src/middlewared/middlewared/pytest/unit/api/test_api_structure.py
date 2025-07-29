import importlib
import inspect
import os
import pathlib
import pkgutil

import pytest

import middlewared.api
from middlewared.api.base import BaseModel


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

    """
    if not docstr:
        if must_have:
            # Either a docstring or `Field(description=...)` will do
            return "Must have description"
        return
    if any(c in docstr for c in ["*", "-"]):
        # Just assume Markdown and skip rules check
        return

    docstr = docstr.strip()
    if docstr[0].islower() and docstr.partition(" ")[0] not in {"pCloud", "iSCSI"}:
        return "Docstring cannot start with lowercase letter"
    if not docstr.endswith("."):
        return "Docstring must end with a period"
    if any(line[-1] not in (".", ":") for line in docstr.splitlines() if line):
        return r"Use '\' at ends of lines to wrap text"


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
