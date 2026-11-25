from typing import Any, TYPE_CHECKING

from middlewared.common.block_storage import BlockStorageDelegate, BlockStorageKind, BlockStorageUse

if TYPE_CHECKING:
    from middlewared.main import Middleware


def extent_block_storage(extent: dict[str, Any]) -> tuple[BlockStorageKind, str]:
    """The `(kind, path)` an extent claims, spelled the way `iscsi.extent` stores it."""
    if extent["type"] == "DISK":
        return "ZVOL", extent["path"]

    return "FILE", extent["path"]


class ISCSIExtentBlockStorageDelegate(BlockStorageDelegate):
    namespace = "iscsi.extent"

    async def get_in_use(self) -> list[BlockStorageUse]:
        uses = []
        for extent in await self.middleware.call("iscsi.extent.query"):
            kind, path = extent_block_storage(extent)
            uses.append(
                BlockStorageUse(
                    kind=kind,
                    path=path,
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
