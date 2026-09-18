"""Import every API version the server can serve.

middlewared imports the newest API version at startup. It imports every older
version on demand, the first time a client asks for that version. A
module-level error in an older version therefore survives the build, the
install and the boot. It surfaces when that one client connects.

Importing catches what parsing cannot: a name that no longer exists, a model
whose field type is invalid, anything else that raises while the module loads.

The versions are discovered the way ``Middleware._create_apis`` discovers them,
and the models are collected the way ``ModuleModelProvider`` collects them, so
a version that passes here is a version the server can load.

Usage::

    python -m middlewared.test.linter.api_import_check [VERSION ...]

A ``VERSION`` is a package name under ``middlewared/api/``, such as
``v26_0_0``. Without arguments every version is checked.
"""

import importlib
import os
import pathlib
import sys
import traceback

import middlewared
from middlewared.api.base.handler.model_provider import models_from_module

API_DIR = pathlib.Path(os.path.dirname(os.path.abspath(middlewared.__file__))) / "api"

RESET, BOLD, RED, DIM = "\x1b[0m", "\x1b[1m", "\x1b[91m", "\x1b[2m"


def discover_versions() -> list[str]:
    """Return every API version package name, in the order the server sorts them."""
    return sorted(
        entry.name
        for entry in API_DIR.iterdir()
        if entry.name.startswith("v") and entry.is_dir() and (entry / "__init__.py").exists()
    )


def check_version(version: str) -> tuple[int, str | None]:
    """Import one version. Return its model count, and a traceback when it fails."""
    try:
        module = importlib.import_module(f"middlewared.api.{version}")
        return len(models_from_module(module)), None
    except BaseException:
        return 0, traceback.format_exc()


def main(argv: list[str]) -> int:
    versions = argv
    if not versions:
        versions = discover_versions()
        if not versions:
            raise SystemExit(f"error: no API versions found in {API_DIR}")

    color = sys.stdout.isatty()
    failed = []
    for version in versions:
        count, error = check_version(version)
        if error is None:
            print(f"  {version}: {count} models")
            continue

        failed.append(version)
        location = f"middlewared/api/{version}"
        if color:
            location = f"{BOLD}{location}{RESET}"
            print(f"{location}: {RED}error{RESET}: failed to import\n{DIM}{error}{RESET}")
        else:
            print(f"{location}: error: failed to import\n{error}")

    if failed:
        print(f"Failed to import {len(failed)} of {len(versions)} API version(s): {', '.join(failed)}")
        return 1

    print(f"Imported {len(versions)} API version(s): no errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
