from __future__ import annotations

import typing

from middlewared.plugins.zfs.delegates import ZFSResourceDelegate
from middlewared.plugins.zfs.zvol_utils import zvol_name_to_path

if typing.TYPE_CHECKING:
    from middlewared.api.current import ZFSResourceEntry
    from middlewared.plugins.zfs.set_rules import SetContext
    from middlewared.service_exception import ValidationErrors

__all__ = ("ISCSIExtentDelegate",)


class ISCSIExtentDelegate(ZFSResourceDelegate):
    name = "iscsi.extent"
    types = frozenset({"VOLUME"})
    triggers = frozenset({"volsize", "readonly", "snapdev"})

    async def validate_set(self, state: SetContext, verrors: ValidationErrors) -> None:
        """Refuse to hide snapshot devices that back an extent."""
        if not state.snapshot_devices or not state.changed("snapdev") or state.effective("snapdev") != "hidden":
            return

        paths = [zvol_name_to_path(name).removeprefix("/dev/") for name in sorted(state.snapshot_devices)]
        if await self.middleware.call("iscsi.extent.query", [["path", "in", paths]], {"select": ["path"]}):
            verrors.add(
                state.attribute("snapdev"),
                f"{state.path!r} has snapshots which have attachments being used. Before marking it "
                "as HIDDEN, remove attachment usages.",
            )

    async def after_set(self, state: SetContext, entry: ZFSResourceEntry) -> None:
        """Bring the extent backed by this volume in line with its new size and readonly state."""
        if state.changed("volsize"):
            await self.middleware.call("iscsi.global.resync_lun_size_for_zvol", state.path)
        if "readonly" in state.touched():
            await self.middleware.call(
                "iscsi.global.resync_readonly_property_for_zvol", state.path, state.effective("readonly")
            )
