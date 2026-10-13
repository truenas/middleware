from __future__ import annotations

import asyncio
import errno
import inspect
from itertools import groupby
from typing import TYPE_CHECKING, Any

from middlewared.api.current import PoolAttachment, ZFSResourceQuery
from middlewared.service_exception import ValidationError

from .utils import has_internal_path, resource_mountpoint

if TYPE_CHECKING:
    from middlewared.common.attachment import FSAttachmentDelegate, UnlockedDataset
    from middlewared.service import ServiceContext

__all__ = (
    "DELEGATES",
    "attachments",
    "attachments_with_path",
    "cleanup_all_after_pool_destroy",
    "delegates_in_start_order",
    "delegates_in_stop_order",
    "delete_all",
    "query_all",
    "register",
    "start_all_after_reimport",
    "start_all_after_unlock",
    "stop_all",
)

DELEGATES: list[FSAttachmentDelegate[Any]] = []


def register(delegate: FSAttachmentDelegate[Any]) -> None:
    if inspect.iscoroutinefunction(delegate.validate_set) or inspect.iscoroutinefunction(delegate.after_set):
        raise TypeError(f"{type(delegate).__name__}: validate_set and after_set must be synchronous")
    DELEGATES.append(delegate)


def delegates_in_start_order() -> list[FSAttachmentDelegate[Any]]:
    return sorted(DELEGATES, key=lambda d: d.priority, reverse=True)


def delegates_in_stop_order() -> list[FSAttachmentDelegate[Any]]:
    return sorted(DELEGATES, key=lambda d: d.priority)


async def _stop_one(delegate: FSAttachmentDelegate[Any], path: str) -> None:
    if attachments := await delegate.query(path, True):
        await delegate.stop(attachments)


async def stop_all(path: str | None) -> None:
    if not path:
        return
    for _, group in groupby(delegates_in_stop_order(), key=lambda d: d.priority):
        await asyncio.gather(*(_stop_one(d, path) for d in group))


async def delete_all(path: str) -> None:
    for delegate in delegates_in_stop_order():
        if attachments := await delegate.query(path, True):
            await delegate.delete(attachments)


async def start_all_after_reimport(context: ServiceContext, path: str) -> None:
    for delegate in delegates_in_start_order():
        # The pool is already imported, so a delegate failure here must not abort the reimport
        try:
            await delegate.start_on_import(path)
        except Exception:
            context.logger.error("%s: failed to start attachments after pool reimport", delegate.name, exc_info=True)


async def start_all_after_unlock(context: ServiceContext, datasets: list[UnlockedDataset]) -> None:
    if not datasets:
        return
    for delegate in delegates_in_start_order():
        # The datasets are already unlocked and mounted, so a delegate failure here must not abort
        # the unlock job before its encryption records are persisted
        try:
            await delegate.start_on_unlock(datasets)
        except Exception:
            context.logger.error("%s: failed to start attachments after unlock", delegate.name, exc_info=True)


async def cleanup_all_after_pool_destroy(context: ServiceContext, path: str) -> None:
    for delegate in delegates_in_stop_order():
        # The pool is already gone, so a delegate failure here must not fail the export job
        try:
            await delegate.destroy(path)
        except Exception:
            context.logger.error(
                "%s: failed to clean up attachments after the pool was destroyed", delegate.name, exc_info=True
            )


async def query_all(
    context: ServiceContext, path: str | None, check_parent: bool = False, exact_match: bool = False
) -> list[dict[str, Any]]:
    if isinstance(path, str) and not path.startswith("/mnt/"):
        context.logger.warning("%s: unexpected path not located within pool mountpoint", path)
    if not path:
        return []
    options = {"check_parent": check_parent, "exact_match": exact_match}
    result: list[dict[str, Any]] = []
    for delegate in DELEGATES:
        if names := [await delegate.get_attachment_name(a) for a in await delegate.query(path, True, options)]:
            result.append({"type": delegate.title, "service": delegate.service, "attachments": names})
    return result


def attachments_with_path(
    context: ServiceContext, path: str | None, check_parent: bool = False, exact_match: bool = False
) -> list[dict[str, Any]]:
    return context.run_coroutine(query_all(context, path, check_parent, exact_match))


def attachments(context: ServiceContext, path: str) -> list[PoolAttachment]:
    rows: list[dict[str, Any]] = []
    if not has_internal_path(path):
        rows = context.call_sync2(
            context.s.zfs.resource.list_impl, ZFSResourceQuery(paths=[path], properties=["mountpoint"])
        )
    if not rows:
        raise ValidationError("zfs.resource.attachments.path", f"{path!r} does not exist", errno.ENOENT)
    if (mountpoint := resource_mountpoint(rows[0])) is None:
        return []
    return [PoolAttachment(**entry) for entry in attachments_with_path(context, mountpoint)]
