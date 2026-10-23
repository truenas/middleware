from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .constants import NO_LOGIN_SHELL

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("shell_choices",)


def shell_choices(context: ServiceContext, group_ids: list[int]) -> dict[str, str]:
    gids = {
        group["gid"]
        for group in context.middleware.call_sync(
            "datastore.query",
            "account.bsdgroups",
            [("id", "in", group_ids)],
            {"prefix": "bsdgrp_"},
        )
    }

    shells = {
        NO_LOGIN_SHELL: "nologin",
    }
    if context.call_sync2(context.s.privilege.privileges_for_groups, "local_groups", gids):
        shells.update(
            {
                "/usr/bin/cli": "TrueNAS CLI",  # installed via midcli
                "/usr/bin/cli_console": "TrueNAS Console",  # installed via midcli
            }
        )

    with open("/etc/shells") as f:
        for shell in filter(lambda x: x.startswith("/usr/bin"), f):
            # on scale /etc/shells has duplicate entries like (/bin/sh, /usr/bin/sh) (/bin/bash, /usr/bin/bash) etc.
            # The entries that point to the same basename are the same binary.
            # The /usr/bin/ path is the "newer" place to put binaries so we'll use those entries.
            shell = shell.strip()
            shells[shell] = os.path.basename(shell)

    return shells
