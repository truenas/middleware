from __future__ import annotations

import asyncio
from itertools import groupby
from typing import TYPE_CHECKING

from middlewared.api.current import PoolAttachment

if TYPE_CHECKING:
    from middlewared.common.attachment import FSAttachmentDelegate
    from middlewared.service import ServiceContext

from .utils import dataset_mountpoint


async def attachments_impl(ctx: ServiceContext, oid: str) -> list[PoolAttachment]:
    dataset = await ctx.call2(ctx.s.pool.dataset.get_instance_quick, oid)
    if mountpoint := dataset_mountpoint(dataset):
        return await attachments_with_path(ctx, mountpoint)
    return []


async def attachments_with_path(
    ctx: ServiceContext,
    path: str,
    check_parent: bool = False,
    exact_match: bool = False
) -> list[PoolAttachment]:
    if isinstance(path, str) and not path.startswith('/mnt/'):
        ctx.logger.warning('%s: unexpected path not located within pool mountpoint', path)

    if not path:
        return []

    # Access attachment_delegates from the service instance via type-safe call
    attachment_delegates = await ctx.call2(ctx.s.pool.dataset.get_attachment_delegates)

    result = []
    options = {'check_parent': check_parent, 'exact_match': exact_match}
    for delegate in attachment_delegates:
        attachments = [
            await delegate.get_attachment_name(attachment)
            for attachment in await delegate.query(path, True, options)
        ]
        if attachments:
            result.append(
                PoolAttachment(
                    type=delegate.title,
                    service=delegate.service,
                    attachments=attachments
                )
            )

    return result


async def stop_attachment_delegates_impl(ctx: ServiceContext, path: str | None) -> None:
    if not path:
        return

    delegates = await get_attachment_delegates_for_stop(ctx)
    for _, group in groupby(delegates, key=lambda d: d.priority):
        group_list = list(group)

        async def stop_delegate(delegate: FSAttachmentDelegate):
            if attachments := await delegate.query(path, True):
                await delegate.stop(attachments)

        await asyncio.gather(*[stop_delegate(dg) for dg in group_list])


async def get_attachment_delegates_for_start(ctx: ServiceContext) -> list[FSAttachmentDelegate]:
    attachment_delegates = await ctx.call2(ctx.s.pool.dataset.get_attachment_delegates)
    return sorted(attachment_delegates, key=lambda d: d.priority, reverse=True)


async def get_attachment_delegates_for_stop(ctx: ServiceContext) -> list[FSAttachmentDelegate]:
    attachment_delegates = await ctx.call2(ctx.s.pool.dataset.get_attachment_delegates)
    return sorted(attachment_delegates, key=lambda d: d.priority)
