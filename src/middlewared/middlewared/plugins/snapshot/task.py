from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.service_exception import CallError

if TYPE_CHECKING:
    from middlewared.service.context import ServiceContext


MAX_COUNT = 512
MAX_TOTAL_COUNT = 10000


def max_count() -> int:
    # There is a limit to how many snapshots Windows will present to users through File Explorer. If we respond
    # with too many, then File Explorer will show no snapshots available.
    return MAX_COUNT


def max_total_count() -> int:
    # Having too many snapshots results in various performance complications (mainly, when listing them).
    # This is a random round number that is large enough and does not cause issues in most use cases.
    return MAX_TOTAL_COUNT


async def run(ctx: ServiceContext, id_: int) -> None:
    task = await ctx.call2(ctx.s.pool.snapshottask.get_instance, id_)

    if not task.enabled:
        raise CallError("Task is not enabled")

    await ctx.middleware.call("zettarepl.run_periodic_snapshot_task", task.id)
