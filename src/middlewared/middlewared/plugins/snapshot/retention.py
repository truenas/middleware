from __future__ import annotations

from collections import defaultdict
import errno
from typing import TYPE_CHECKING

from middlewared.api.current import (
    PeriodicSnapshotTaskEntry, PoolSnapshotTaskUpdateWillChangeRetentionFor,
)
from middlewared.service_exception import CallError

if TYPE_CHECKING:
    from middlewared.service.context import ServiceContext


async def removal_date_property(ctx: ServiceContext) -> str:
    host_id = await ctx.middleware.call("system.host_id")
    return f"org.truenas:destroy_at_{host_id[:8]}"


async def fixate_removal_date(
    ctx: ServiceContext, datasets: dict[str, list[str]], task: PeriodicSnapshotTaskEntry,
) -> None:
    await ctx.middleware.call("zettarepl.fixate_removal_date", datasets, task)


async def update_will_change_retention_for(
    ctx: ServiceContext,
    id_: int,
    data: PoolSnapshotTaskUpdateWillChangeRetentionFor,
) -> dict[str, list[str]]:
    old = await ctx.call2(ctx.s.pool.snapshottask.get_instance, id_)
    new = old.updated(data)

    result: dict[str, list[str]] = defaultdict(list)
    if old != new:
        try:
            old_snapshots = await ctx.middleware.call("zettarepl.periodic_snapshot_task_snapshots", old)
        except CallError as e:
            if e.errno == errno.ENOENT:
                return result

            raise

        new_snapshots = await ctx.middleware.call("zettarepl.periodic_snapshot_task_snapshots", new)
        if diff := old_snapshots - new_snapshots:
            for snapshot in sorted(diff):
                dataset, snapshot = snapshot.split("@", 1)
                result[dataset].append(snapshot)

    return result


async def delete_will_change_retention_for(
    ctx: ServiceContext,
    id_: int,
) -> dict[str, list[str]]:
    task = await ctx.call2(ctx.s.pool.snapshottask.get_instance, id_)

    result: dict[str, list[str]] = defaultdict(list)
    try:
        snapshots = await ctx.middleware.call("zettarepl.periodic_snapshot_task_snapshots", task)
    except CallError as e:
        if e.errno == errno.ENOENT:
            return result

        raise

    for snapshot in sorted(snapshots):
        dataset, snapshot = snapshot.split("@", 1)
        result[dataset].append(snapshot)

    return result
