import asyncio

from middlewared.common.block_storage import (
    BlockStorageAttachment,
    BlockStorageDelegate,
    BlockStorageUse,
    canonical_key,
)
from middlewared.service import Service, ValidationErrors


class BlockStorageService(Service):
    DELEGATES: dict[str, BlockStorageDelegate] = {}

    class Config:
        namespace = "blockstorage"
        private = True

    async def register_attachment_delegate(self, delegate: BlockStorageDelegate) -> None:
        if delegate.namespace in self.DELEGATES:
            raise ValueError(f"{delegate.namespace!r} delegate is already registered with Block Storage Service")
        self.DELEGATES[delegate.namespace] = delegate

    async def get_in_use(
        self,
        kind: str | None = None,
        skip_namespace: str | None = None,
    ) -> list[BlockStorageAttachment]:
        delegates = [delegate for delegate in self.DELEGATES.values() if delegate.namespace != skip_namespace]
        results = await asyncio.gather(*(delegate.get_in_use() for delegate in delegates))
        uses = [
            (delegate.namespace, use)
            for delegate, result in zip(delegates, results)
            for use in result
            if kind is None or use.kind == kind
        ]

        return await self.middleware.run_in_thread(self._attachments, uses)

    def _attachments(self, uses: list[tuple[str, BlockStorageUse]]) -> list[BlockStorageAttachment]:
        return [
            BlockStorageAttachment(
                namespace=namespace,
                key=canonical_key(use.kind, use.path),
                kind=use.kind,
                path=use.path,
                id=use.id,
                description=use.description,
                data=use.data,
            )
            for namespace, use in uses
        ]

    async def in_use_by(
        self,
        kind: str,
        path: str,
        exclude: tuple[str, int] | None = None,
        whitelist_namespace: str | None = None,
    ) -> BlockStorageAttachment | None:
        exclude_key: tuple[str, int] | None = None
        if exclude is not None:
            exclude_key = (exclude[0], exclude[1])

        key = await self.middleware.run_in_thread(canonical_key, kind, path)
        for attachment in await self.get_in_use(kind, whitelist_namespace):
            if attachment.key == key and (attachment.namespace, attachment.id) != exclude_key:
                return attachment

        return None

    async def validate(
        self,
        schema: str,
        kind: str,
        path: str,
        exclude: tuple[str, int] | None = None,
        raise_error: bool = False,
        whitelist_namespace: str | None = None,
    ) -> ValidationErrors | None:
        verrors = ValidationErrors()
        if attachment := await self.in_use_by(kind, path, exclude, whitelist_namespace):
            if kind == "ZVOL":
                noun = "Disk"
            else:
                noun = "File"
            verrors.add(schema, f"{noun} currently in use by {attachment.description}")

        if raise_error:
            verrors.check()
            return None

        return verrors
