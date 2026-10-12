from __future__ import annotations

from datetime import time as _time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from zettarepl.definition.definition import Definition

from middlewared.api.current import PeriodicSnapshotTaskEntry
from middlewared.service_exception import CallError
from middlewared.utils.string import make_sentence
from middlewared.utils.time_utils import utc_now
from middlewared.utils.timezone_choices import effective_timezone

from .state import PERIODIC_SNAPSHOT_TASK_STATE, REPLICATION_TASK_STATE
from .transport import define_transport

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


class HoldReplicationTaskException(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__()


def lifetime_timedelta(value: int, unit: str) -> timedelta:
    if unit == "HOUR":
        return timedelta(hours=value)

    if unit == "DAY":
        return timedelta(days=value)

    if unit == "WEEK":
        return timedelta(weeks=value)

    if unit == "MONTH":
        return timedelta(days=value * 30)

    if unit == "YEAR":
        return timedelta(days=value * 365)

    raise ValueError(f"Invalid lifetime unit: {unit!r}")


def timedelta_iso8601(value: timedelta) -> str:
    return f"PT{int(value.total_seconds())}S"


def lifetime_iso8601(value: int, unit: str) -> str:
    return timedelta_iso8601(lifetime_timedelta(value, unit))


def replication_task_exclude(replication_task: dict[str, Any]) -> list[str]:
    exclude = list(replication_task["exclude"])
    if replication_task["recursive"] and not replication_task["replicate"]:
        for ds in replication_task["source_datasets"]:
            # Exclude all possible FreeNAS system datasets
            if "/" not in ds:
                exclude.append(f"{ds}/.system")

    return exclude


def zettarepl_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    schedule = {k.replace("_", "-"): v for k, v in schedule.items()}
    schedule["day-of-month"] = schedule.pop("dom")
    schedule["day-of-week"] = schedule.pop("dow")
    for k in ["begin", "end"]:
        if k in schedule and isinstance(schedule[k], _time):
            schedule[k] = str(schedule[k])[:5]

    return schedule


def periodic_snapshot_task_definition(periodic_snapshot_task: PeriodicSnapshotTaskEntry) -> dict[str, Any]:
    return {
        "dataset": periodic_snapshot_task.dataset,
        "recursive": periodic_snapshot_task.recursive,
        "exclude": periodic_snapshot_task.exclude,
        "lifetime": lifetime_iso8601(periodic_snapshot_task.lifetime_value, periodic_snapshot_task.lifetime_unit),
        "naming-schema": periodic_snapshot_task.naming_schema,
        "schedule": zettarepl_schedule(periodic_snapshot_task.schedule.model_dump()),
        "allow-empty": periodic_snapshot_task.allow_empty,
    }


def hold_task_reason(pools: dict[str, dict[str, Any]], dataset: str) -> str | None:
    pool = dataset.split("/")[0]

    if pool not in pools:
        return f"Pool {pool} does not exist"

    if pools[pool]["status"] == "OFFLINE":
        return f"Pool {pool} is offline"

    return None


async def build_definition(
    context: ServiceContext,
    onetime_replication_tasks: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = await context.middleware.call("replication.config.config")
    # Sanitize against a stale DB value left over from an upgrade (e.g. a legacy alias like "Japan") -- the
    # ZoneInfo lookup downstream would otherwise raise ZoneInfoNotFoundError.
    timezone = effective_timezone((await context.middleware.call("system.general.config"))["timezone"])

    pools = {pool["name"]: pool for pool in await context.middleware.call("pool.query")}

    hold_tasks: dict[str, str] = {}

    periodic_snapshot_tasks = {}
    for periodic_snapshot_task in await context.call2(context.s.pool.snapshottask.query, [["enabled", "=", True]]):
        if reason := hold_task_reason(pools, periodic_snapshot_task.dataset):
            hold_tasks[PERIODIC_SNAPSHOT_TASK_STATE.task_id(periodic_snapshot_task.id)] = reason
            continue

        periodic_snapshot_tasks[f"task_{periodic_snapshot_task.id}"] = periodic_snapshot_task_definition(
            periodic_snapshot_task,
        )

    replication_tasks = {}
    for entry in await context.call2(context.s.replication.query):
        # `replication_task_definition` builds a zettarepl-library task definition and is shared with one-time
        # tasks (`onetime_replication_tasks`), which are plain dicts of a different shape. Dump the model to a
        # dict here so both paths feed it the same representation.
        replication_task = entry.model_dump(expose_secrets=True)
        try:
            replication_tasks[f"task_{replication_task['id']}"] = await replication_task_definition(
                context, pools, replication_task
            )
        except HoldReplicationTaskException as e:
            hold_tasks[REPLICATION_TASK_STATE.task_id(replication_task["id"])] = e.reason

    for job_id, replication_task in onetime_replication_tasks.items():
        try:
            replication_tasks[f"job_{job_id}"] = await replication_task_definition(context, pools, replication_task)
        except HoldReplicationTaskException as e:
            hold_tasks[f"job_{job_id}"] = e.reason

    definition = {
        "max-parallel-replication-tasks": config.max_parallel_replication_tasks,
        "timezone": timezone,
        "periodic-snapshot-tasks": periodic_snapshot_tasks,
        "replication-tasks": replication_tasks,
    }

    # Test if does not cause exceptions
    Definition.from_data(definition, raise_on_error=False)

    return definition, {
        task_id: {
            "state": "HOLD",
            "datetime": utc_now(),
            "reason": make_sentence(reason),
        }
        for task_id, reason in hold_tasks.items()
    }


async def replication_task_definition(
    context: ServiceContext,
    pools: dict[str, dict[str, Any]],
    replication_task: dict[str, Any],
) -> dict[str, Any]:
    if replication_task["direction"] == "PUSH":
        for source_dataset in replication_task["source_datasets"]:
            if reason := hold_task_reason(pools, source_dataset):
                raise HoldReplicationTaskException(reason)

    if replication_task["direction"] == "PULL":
        if reason := hold_task_reason(pools, replication_task["target_dataset"]):
            raise HoldReplicationTaskException(reason)

    if replication_task["transport"] != "LOCAL":
        if not await context.middleware.call("network.general.can_perform_activity", "replication"):
            raise HoldReplicationTaskException("Replication network activity is disabled")

    try:
        transport = await define_transport(
            context,
            replication_task["transport"],
            (replication_task["ssh_credentials"] or {}).get("id"),
            replication_task["netcat_active_side"],
            replication_task["netcat_active_side_listen_address"],
            replication_task["netcat_active_side_port_min"],
            replication_task["netcat_active_side_port_max"],
            replication_task["netcat_passive_side_connect_address"],
            replication_task["sudo"],
        )
    except CallError as e:
        raise HoldReplicationTaskException(e.errmsg)

    properties_exclude = replication_task["properties_exclude"].copy()
    properties_override = replication_task["properties_override"].copy()
    for property_ in ["mountpoint", "sharenfs", "sharesmb"]:
        if property_ == "mountpoint" and not replication_task.get("exclude_mountpoint_property", True):
            continue

        if property_ not in properties_override:
            if property_ not in properties_exclude:
                properties_exclude.append(property_)

    definition = {
        "direction": replication_task["direction"].lower(),
        "transport": transport,
        "source-dataset": replication_task["source_datasets"],
        "target-dataset": replication_task["target_dataset"],
        "recursive": replication_task["recursive"],
        "exclude": replication_task_exclude(replication_task),
        "properties": replication_task["properties"],
        "properties-exclude": properties_exclude,
        "properties-override": properties_override,
        "replicate": replication_task["replicate"],
        "periodic-snapshot-tasks": [
            f"task_{periodic_snapshot_task['id']}"
            for periodic_snapshot_task in replication_task["periodic_snapshot_tasks"]
        ],
        "auto": replication_task["auto"] and replication_task["enabled"],
        "only-matching-schedule": replication_task["only_matching_schedule"] and replication_task["enabled"],
        "allow-from-scratch": replication_task["allow_from_scratch"],
        "only-from-scratch": replication_task.get("only_from_scratch", False),
        "readonly": replication_task["readonly"].lower(),
        "mount": replication_task.get("mount", True),
        "hold-pending-snapshots": replication_task["hold_pending_snapshots"],
        "retention-policy": replication_task["retention_policy"].lower(),
        "large-block": replication_task["large_block"],
        "embed": replication_task["embed"],
        "compressed": replication_task["compressed"],
        "retries": replication_task["retries"],
        "logging-level": (replication_task["logging_level"] or "NOTSET").lower(),
    }

    if replication_task["encryption"]:
        if replication_task["encryption_inherit"]:
            definition["encryption"] = "inherit"
        else:
            definition["encryption"] = {
                "key": replication_task["encryption_key"],
                "key-format": replication_task["encryption_key_format"].lower(),
                "key-location": replication_task["encryption_key_location"],
            }
    if replication_task["naming_schema"]:
        definition["naming-schema"] = replication_task["naming_schema"]
    if replication_task["also_include_naming_schema"]:
        definition["also-include-naming-schema"] = replication_task["also_include_naming_schema"]
    if replication_task["name_regex"]:
        definition["name-regex"] = replication_task["name_regex"]
    if replication_task["schedule"] is not None and replication_task["enabled"]:
        definition["schedule"] = zettarepl_schedule(replication_task["schedule"])
    if replication_task["restrict_schedule"] is not None:
        definition["restrict-schedule"] = zettarepl_schedule(replication_task["restrict_schedule"])
    if replication_task["lifetime_value"] is not None and replication_task["lifetime_unit"] is not None:
        definition["lifetime"] = lifetime_iso8601(replication_task["lifetime_value"], replication_task["lifetime_unit"])
    if replication_task["lifetimes"]:
        definition["lifetimes"] = {
            f"lifetime_{i}": {
                "schedule": zettarepl_schedule(lifetime["schedule"]),
                "lifetime": lifetime_iso8601(lifetime["lifetime_value"], lifetime["lifetime_unit"]),
            }
            for i, lifetime in enumerate(replication_task["lifetimes"])
        }
    if replication_task["compression"] is not None:
        definition["compression"] = replication_task["compression"].lower()
    if replication_task["speed_limit"] is not None:
        definition["speed-limit"] = replication_task["speed_limit"]

    return definition
