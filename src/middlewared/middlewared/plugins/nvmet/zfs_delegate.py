from __future__ import annotations

import os
import typing

from middlewared.plugins.zfs.delegates import ZFSResourceDelegate
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name

if typing.TYPE_CHECKING:
    from middlewared.api.current import ZFSResourceEntry
    from middlewared.plugins.zfs.set_rules import SetContext
    from middlewared.service_exception import ValidationErrors

__all__ = ("NVMetNamespaceDelegate",)


class NVMetNamespaceDelegate(ZFSResourceDelegate):
    name = "nvmet.namespace"
    types = frozenset({"VOLUME"})
    triggers = frozenset({"volsize", "snapdev"})

    async def validate_set(self, state: SetContext, verrors: ValidationErrors) -> None:
        """Refuse to hide snapshot devices that back a namespace."""
        if not state.snapshot_devices or not state.changed("snapdev") or state.effective("snapdev") != "hidden":
            return

        namespaces = await self.middleware.call(
            "nvmet.namespace.query", [["device_type", "=", "ZVOL"]], {"select": ["device_path"]}
        )
        if any(
            zvol_path_to_name(os.path.join("/dev", ns["device_path"])) in state.snapshot_devices for ns in namespaces
        ):
            verrors.add(
                state.attribute("snapdev"),
                f"{state.path!r} has snapshots which have attachments being used. Before marking it "
                "as HIDDEN, remove attachment usages.",
            )

    async def after_set(self, state: SetContext, entry: ZFSResourceEntry) -> None:
        """Let connected hosts see the new size of the volume."""
        if state.changed("volsize"):
            await self.middleware.call("nvmet.namespace.resync_lun_size_for_zvol", state.path)
