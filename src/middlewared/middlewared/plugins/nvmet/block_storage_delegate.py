from typing import TYPE_CHECKING

from middlewared.common.block_storage import BlockStorageDelegate, BlockStorageUse

if TYPE_CHECKING:
    from middlewared.main import Middleware


class NVMetNamespaceBlockStorageDelegate(BlockStorageDelegate):
    namespace = "nvmet.namespace"

    async def get_in_use(self) -> list[BlockStorageUse]:
        return [
            BlockStorageUse(
                kind=namespace["device_type"],
                path=namespace["device_path"],
                id=namespace["id"],
                description=f"NVMe-oF subsystem {namespace['subsys']['name']} NSID {namespace['nsid']}",
                data=namespace,
            )
            for namespace in await self.middleware.call("nvmet.namespace.query")
        ]


async def setup(middleware: "Middleware") -> None:
    await middleware.call2(
        middleware.services.blockstorage.register_attachment_delegate, NVMetNamespaceBlockStorageDelegate(middleware)
    )
