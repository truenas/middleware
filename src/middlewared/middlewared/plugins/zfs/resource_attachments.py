from __future__ import annotations

import asyncio
import errno
from itertools import groupby
from typing import TYPE_CHECKING, Any

from middlewared.api.current import PoolAttachment, ZFSResourceQuery
from middlewared.service_exception import ValidationError

from .utils import has_internal_path, resource_mountpoint

if TYPE_CHECKING:
    from middlewared.common.attachment import FSAttachmentDelegate
    from middlewared.service import ServiceContext

__all__ = ("DELEGATES", "attachments", "attachments_with_path", "for_start", "for_stop", "register", "stop")

DELEGATES: list[FSAttachmentDelegate[Any]] = []


def register(delegate: FSAttachmentDelegate[Any]) -> None:
    DELEGATES.append(delegate)


def for_start() -> list[FSAttachmentDelegate[Any]]:
    return sorted(DELEGATES, key=lambda d: d.priority, reverse=True)


def for_stop() -> list[FSAttachmentDelegate[Any]]:
    return sorted(DELEGATES, key=lambda d: d.priority)


async def _stop(delegate: FSAttachmentDelegate[Any], path: str) -> None:
    if attachments := await delegate.query(path, True):
        await delegate.stop(attachments)


async def stop(path: str | None) -> None:
    if not path:
        return
    for _, group in groupby(for_stop(), key=lambda d: d.priority):
        await asyncio.gather(*(_stop(d, path) for d in group))


async def attachments_with_path(
    context: ServiceContext, path: str | None, check_parent: bool = False, exact_match: bool = False
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(path, str) and not path.startswith("/mnt/"):
        context.logger.warning("%s: unexpected path not located within pool mountpoint", path)
    if not path:
        return result
    options = {"check_parent": check_parent, "exact_match": exact_match}
    for delegate in DELEGATES:
        if names := [await delegate.get_attachment_name(a) for a in await delegate.query(path, True, options)]:
            result.append({"type": delegate.title, "service": delegate.service, "attachments": names})
    return result


async def attachments(context: ServiceContext, path: str) -> list[PoolAttachment]:
    rows: list[dict[str, Any]] = []
    if not has_internal_path(path):
        rows = await context.call2(
            context.s.zfs.resource.list_impl, ZFSResourceQuery(paths=[path], properties=["mountpoint"])
        )
    if not rows:
        raise ValidationError("zfs.resource.attachments.path", f"{path!r} does not exist", errno.ENOENT)
    if (mountpoint := resource_mountpoint(rows[0])) is None:
        return []
    return [PoolAttachment(**entry) for entry in await attachments_with_path(context, mountpoint)]
