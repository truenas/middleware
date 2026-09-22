from __future__ import annotations

import typing

from middlewared.plugins.zfs.delegates import ZFSResourceDelegate

if typing.TYPE_CHECKING:
    from middlewared.plugins.zfs.set_rules import SetContext
    from middlewared.service_exception import ValidationErrors

__all__ = ("SMBShareDelegate",)


class SMBShareDelegate(ZFSResourceDelegate):
    name = "smb.share"
    types = frozenset({"FILESYSTEM"})
    triggers = frozenset({"acltype"})

    async def validate_set(self, state: SetContext, verrors: ValidationErrors) -> None:
        """Refuse to change the ACL type under enabled SMB shares."""
        if not state.changed("acltype"):
            return

        attachments = await self.middleware.call("pool.dataset.attachments", state.path)
        if names := [name for a in attachments if a["type"] == "SMB Share" for name in a["attachments"]]:
            verrors.add(
                state.attribute("acltype"),
                "This dataset is hosting SMB shares. Before acltype can be updated the following shares must be "
                f"disabled: {', '.join(names)}. The shares may be re-enabled after the change.",
            )
