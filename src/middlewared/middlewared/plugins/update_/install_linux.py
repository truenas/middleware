from __future__ import annotations

import json
import logging
import os
import typing

from middlewared.plugins.config import UPLOADED_DB_PATH
from middlewared.service import CallError, ServiceContext
from middlewared.utils import sw_info

from .utils import can_update
from .utils_linux import mount_update

if typing.TYPE_CHECKING:
    from middlewared.job import Job

logger = logging.getLogger(__name__)


def install(
        context: ServiceContext,
        job: Job,
        path: str,
        options: dict[str, typing.Any],
        max_progress: int = 100,
) -> None:
    if os.path.exists(UPLOADED_DB_PATH):
        raise CallError(
            "An unapplied uploaded configuration exists. Please, reboot the system to apply this configuration "
            "before running upgrade."
        )

    state = context.middleware.call_sync("boot.get_state")
    if (
        state["scan"] and
        state["scan"]["function"] == "RESILVER" and
        state["scan"]["state"] == "SCANNING"
    ):
        raise CallError(
            "One or more boot pool devices are currently being resilvered. The upgrade cannot continue "
            "until the resilvering operation is finished."
        )

    if context.middleware.call_sync("smb.config")["stateful_failover"]:
        # CTDB will assert on version mismatch between nodes. Upgrade procedure should be:
        # 1. disabled stateful failover
        # 2. upgrade both nodes
        # 3. enable stateful failover
        raise CallError("Stateful SMB failover must be disabled prior to updating truenas")

    def progress_callback(progress: float, description: str) -> None:
        job.set_progress((0.5 + 0.5 * progress) * max_progress, description)

    progress_callback(0, "Reading update file")
    with mount_update(path) as mounted:
        with open(os.path.join(mounted, "manifest.json")) as f:
            manifest = json.load(f)

        old_version = sw_info().version
        new_version = manifest["version"]
        if old_version == new_version:
            raise CallError(f'You already are using {new_version}')
        if not can_update(old_version, new_version):
            raise CallError(f'Unable to downgrade from {old_version} to {new_version}')

        from .install import install_scale
        install_scale(context, mounted, progress_callback, options)
