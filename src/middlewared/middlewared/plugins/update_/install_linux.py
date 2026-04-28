from __future__ import annotations

from datetime import date
import errno
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
    from middlewared.plugins.truenas.license_utils import LicenseInfo

logger = logging.getLogger(__name__)


def _enforce_lts_gate(manifest: dict, lts_mode: bool, license_info: LicenseInfo | None) -> None:
    """Two checks; both raise CallError(EACCES) on failure.

    1. If LTS mode is on, only LTS-marked images are allowed.
    2. If the image is LTS-marked, the system's license must carry an
       unexpired LTS feature.

    CallError is surfaced via the outer @api_method(audit=...) wrapper of
    update.run / update.manual, so a denial is auto-audited.
    """
    is_lts_image = bool(manifest.get("lts"))

    if lts_mode and not is_lts_image:
        logger.warning("LTS update gate: refusing non-LTS image while LTS mode is enabled")
        raise CallError(
            "LTS mode is enabled; only LTS update images may be installed. "
            "Disable LTS mode or upload an LTS-marked image.",
            errno.EACCES,
        )

    if not is_lts_image:
        return

    today = date.today()
    has_lts = license_info is not None and any(
        f.name == "LTS" and (f.expires_at is None or today <= f.expires_at)
        for f in license_info.features
    )
    if not has_lts:
        lic_id = license_info.id if license_info is not None else "none"
        logger.warning(
            "LTS update gate: license %s does not carry an unexpired LTS feature",
            lic_id,
        )
        raise CallError(
            "This is an LTS update image, but this system's license "
            f"(id: {lic_id}) does not carry an unexpired LTS feature. "
            "Contact sales@truenas.com to upgrade your license.",
            errno.EACCES,
        )


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

        lts_mode = context.middleware.call_sync('update.config_safe').lts
        license_info = context.call_sync2(context.s.truenas.license.info_private)
        _enforce_lts_gate(manifest, lts_mode, license_info)

        old_version = sw_info().version
        new_version = manifest["version"]
        if old_version == new_version:
            raise CallError(f'You already are using {new_version}')
        if not can_update(old_version, new_version):
            raise CallError(f'Unable to downgrade from {old_version} to {new_version}')

        from .install import install_scale
        install_scale(context, mounted, progress_callback, options)
