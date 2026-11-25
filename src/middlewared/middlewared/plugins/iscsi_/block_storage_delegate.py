from typing import TYPE_CHECKING

from middlewared.common.block_storage import BlockStorageDelegate, BlockStorageKind, BlockStorageUse

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ISCSIExtentBlockStorageDelegate(BlockStorageDelegate):
    namespace = "iscsi.extent"

    async def get_in_use(self) -> list[BlockStorageUse]:
        uses = []
        for extent in await self.middleware.call("iscsi.extent.query"):
            kind: BlockStorageKind
            if extent["type"] == "DISK":
                kind = "ZVOL"
            else:
                kind = "FILE"
            uses.append(
                BlockStorageUse(
                    kind=kind,
                    path=extent["path"],
                    id=extent["id"],
                    description=f"iSCSI extent {extent['name']}",
                    data=extent,
                )
            )

        return uses


async def setup(middleware: "Middleware") -> None:
    await middleware.call2(
        middleware.services.blockstorage.register_attachment_delegate, ISCSIExtentBlockStorageDelegate(middleware)
    )
