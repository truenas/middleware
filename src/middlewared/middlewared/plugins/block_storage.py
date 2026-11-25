import asyncio
from typing import TYPE_CHECKING

from middlewared.common.block_storage import (
    BlockStorageAttachment,
    BlockStorageDelegate,
    BlockStorageKind,
    BlockStorageUse,
    canonical_key,
)
from middlewared.service import Service, ValidationErrors

if TYPE_CHECKING:
    from middlewared.main import Middleware


class BlockStorageService(Service):

    class Config:
        namespace = "blockstorage"
        private = True

    def __init__(self, middleware: "Middleware") -> None:
        super().__init__(middleware)
        self.delegates: dict[str, BlockStorageDelegate] = {}

    async def register_attachment_delegate(self, delegate: BlockStorageDelegate) -> None:
        if delegate.namespace in self.delegates:
            raise ValueError(f"{delegate.namespace!r} delegate is already registered with Block Storage Service")
        self.delegates[delegate.namespace] = delegate

    async def get_in_use(
        self,
        kind: BlockStorageKind | None = None,
        skip_namespace: str | None = None,
    ) -> list[BlockStorageAttachment]:
        delegates = [delegate for delegate in self.delegates.values() if delegate.namespace != skip_namespace]
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
        kind: BlockStorageKind,
        path: str,
        whitelist_namespace: str | None = None,
    ) -> BlockStorageAttachment | None:
        key = await self.middleware.run_in_thread(canonical_key, kind, path)
        for attachment in await self.get_in_use(kind, whitelist_namespace):
            if attachment.key == key:
                return attachment

        return None

    async def validate(
        self,
        schema: str,
        kind: BlockStorageKind,
        path: str,
        old: tuple[BlockStorageKind, str] | None = None,
        whitelist_namespace: str | None = None,
    ) -> ValidationErrors:
        """
        Reject `path` if another consumer already has it configured as a disk.

        `old` is the `(kind, path)` the record being validated holds now. A record that keeps its claim is not
        making a new one, so nothing is checked: however the client spells the path, and even if the claim is
        shared with a consumer configured before cross-consumer checks existed. Such records must stay editable.
        """
        verrors = ValidationErrors()
        if old is not None and await self.middleware.run_in_thread(self._same_claim, old, (kind, path)):
            return verrors

        if attachment := await self.in_use_by(kind, path, whitelist_namespace):
            if kind == "ZVOL":
                noun = "Disk"
            else:
                noun = "File"
            verrors.add(schema, f"{noun} currently in use by {attachment.description}")

        return verrors

    @staticmethod
    def _same_claim(old: tuple[BlockStorageKind, str], new: tuple[BlockStorageKind, str]) -> bool:
        return canonical_key(*old) == canonical_key(*new)
