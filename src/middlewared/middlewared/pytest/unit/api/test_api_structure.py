import importlib
import inspect
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
    version_dirs = [
        d.name for d in api_dir.iterdir()
        if d.is_dir() and d.name.startswith('v')
    ]

    # Sort to get the latest version
    latest_version = sorted(version_dirs)[-1]

    # Import and return the latest API package
    module_name = f"middlewared.api.{latest_version}"
    return importlib.import_module(module_name)


def test_api_current_module_exports(current_api_package):
    assert "BaseModel" not in dir(current_api_package), "__all__ must be defined in all API model modules"


def check_docstring(docstr: str | None):
    if not docstr:
        return
    if any(c in docstr for c in ["*", "-"]):
        # Just assume Markdown and skip rules check
        return

    docstr = docstr.strip()
    if docstr[0].islower():
        return "Docstring cannot start with lowercase letter"
    if not docstr.endswith("."):
        return "Docstring must end with a period"


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
                if err := check_docstring(obj.__doc__):  # model's docstring
                    errors.append(SyntaxWarning(f"{name}: {err}"))

                # Iterate over field docstrings
                for field_name, field_info in obj.model_fields.items():
                    if err := check_docstring(field_info.description):
                        errors.append(SyntaxWarning(f"{name}.{field_name}: {err}"))

    if errors:
        raise ExceptionGroup(f"Improper docstring(s) detected in {current_api_package.__name__}", errors)
