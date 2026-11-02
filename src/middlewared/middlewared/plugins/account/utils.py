from __future__ import annotations

import glob
import os
import shlex
from typing import Any

from middlewared.service import ValidationErrors

from .constants import USERNS_IDMAP_DIRECT, USERNS_IDMAP_NONE

__all__ = ("filters_include_ds_accounts", "userns_idmap_to_db", "validate_sudo_commands")


def validate_sudo_commands(commands: list[str]) -> ValidationErrors:
    verrors = ValidationErrors()
    if "ALL" in commands and len(commands) != 1:
        verrors.add(str(commands.index("ALL")), "ALL cannot be used with other commands")
        return verrors

    for i, command in enumerate(commands):
        try:
            executable = shlex.split(command)[0]

            if executable == "ALL":
                continue

            if not executable.startswith("/"):
                raise ValueError("Executable must be an absolute path")

            if os.path.normpath(executable).rstrip("/") != executable.rstrip("/"):
                raise ValueError("Executable path must be normalized")

            paths = glob.glob(executable)
            if not paths:
                raise ValueError(f"No paths matching {executable!r} exist")

            if not executable.endswith("/"):
                for item in paths:
                    if os.path.isfile(item) and os.access(item, os.X_OK):
                        break
                else:
                    raise ValueError(f"None of the paths matching {executable!r} is executable")
        except ValueError as e:
            verrors.add(f"{i}", str(e))

    return verrors


def filters_include_ds_accounts(filters: list[Any]) -> bool:
    """Check for filters limiting to local accounts"""
    for f in filters:
        if len(f) < 3:
            # OR -- assume evaluation for this will result in including DS
            continue

        # Directory services do not provide builtin accounts
        # local explicitly denotes not directory service
        if f[0] in ("local", "builtin"):
            match f[1]:
                case "=":
                    if f[2] is True:
                        return False
                case "!=":
                    if f[2] is False:
                        return False

                case _:
                    pass

    return True


def userns_idmap_to_db(userns_idmap: str | int | None) -> int:
    """Translate the API's subuid/subgid mapping into the integer the datastore stores."""
    match userns_idmap:
        case "DIRECT":
            return USERNS_IDMAP_DIRECT
        case None:
            return USERNS_IDMAP_NONE
        case _:
            return int(userns_idmap)
