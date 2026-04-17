from __future__ import annotations

import errno
import json
import logging
import os
import time
import typing

import truenas_pylicensed

from middlewared.plugins.config import UPLOADED_DB_PATH
from middlewared.service import CallError, ServiceContext
from middlewared.utils import sw_info

from .utils import can_update
from .utils_linux import mount_update

if typing.TYPE_CHECKING:
    from middlewared.job import Job

logger = logging.getLogger(__name__)


def _enforce_lts_gate(mounted: str, manifest: dict) -> None:
    """Layer A: verify manifest.sig and, if the image is LTS-gated, check
    the "LTS" license feature on the running system.

    Raises CallError(EACCES) on any failure. Fail-closed: an LTS-gated
    image with a missing or invalid signature is refused. A non-LTS image
    with a missing signature is allowed for backward compatibility with
    pre-gating builds. CallError is surfaced via the outer
    @api_method(audit=...) wrapper of update.run / update.manual, so a
    denial is already recorded in the audit log.
    """
    sig_path = os.path.join(mounted, "manifest.sig")
    is_lts = bool(manifest.get("lts"))

    try:
        with open(sig_path, "rb") as f:
            sig_bytes = f.read()
    except FileNotFoundError:
        if is_lts:
            logger.warning("LTS update gate: image lacks manifest.sig")
            raise CallError(
                "This LTS update image is missing manifest.sig. "
                "Contact TrueNAS support.",
                errno.EACCES,
            )
        return

    try:
        truenas_pylicensed.verify_update_manifest(manifest, sig_bytes)
    except truenas_pylicensed.SignatureError as e:
        logger.warning("update gate: manifest signature invalid: %s", e)
        raise CallError(f"Update image signature invalid: {e}", errno.EACCES)

    if not is_lts:
        return

    status = truenas_pylicensed.verify()
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if not status.has_feature("LTS", today):
        lic_id = status.id or "none"
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

        _enforce_lts_gate(mounted, manifest)

        old_version = sw_info().version
        new_version = manifest["version"]
        if old_version == new_version:
            raise CallError(f'You already are using {new_version}')
        if not can_update(old_version, new_version):
            raise CallError(f'Unable to downgrade from {old_version} to {new_version}')

        from .install import install_scale
        install_scale(context, mounted, progress_callback, options)
