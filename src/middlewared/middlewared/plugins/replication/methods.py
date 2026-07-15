from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from middlewared.api.base import BaseModel
from middlewared.api.current import (
    ReplicationCountEligibleManualSnapshotsArgs,
    ReplicationCountEligibleManualSnapshotsResult,
    ReplicationCreate,
    ReplicationEntry,
    ReplicationRestoreOptions,
)
from middlewared.plugins.keychain.ssh_pair import KeychainCredentialSSHPairArg
from middlewared.service import CallError, ServiceContext

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job


class ReplicationPairData(BaseModel):
    hostname: str
    public_key: str = Field(alias="public-key")
    user: str | None = None


class ReplicationPairArgs(BaseModel):
    data: ReplicationPairData


class ReplicationPairResult(BaseModel):
    result: dict[str, Any]


async def run_task(context: ServiceContext, job: Job, id_: int, really_run: bool) -> None:
    if really_run:
        task = await context.call2(context.s.replication.get_instance, id_)

        if not task.enabled:
            raise CallError("Task is not enabled")

        if task.state["state"] == "RUNNING":
            raise CallError("Task is already running")

        if task.state["state"] == "HOLD":
            raise CallError("Task is on hold")

    await context.middleware.call("zettarepl.run_replication_task", id_, really_run, job)


async def restore(
    context: ServiceContext,
    app: App,
    id_: int,
    data: ReplicationRestoreOptions,
) -> ReplicationEntry:
    task = await context.call2(context.s.replication.get_instance, id_)

    direction: Literal["PUSH", "PULL"]
    name_regex: str | None = None
    naming_schema: list[str] = []
    also_include_naming_schema: list[str] = []
    if task.direction == "PUSH":
        direction = "PULL"
        if task.name_regex:
            name_regex = task.name_regex
        else:
            naming_schema = list(
                {pst.naming_schema for pst in task.periodic_snapshot_tasks} | set(task.also_include_naming_schema)
            )
    else:
        direction = "PUSH"
        if task.name_regex:
            name_regex = task.name_regex
        else:
            also_include_naming_schema = list(task.naming_schema)

    source_datasets, _ = await context.middleware.call(
        "zettarepl.reverse_source_target_datasets",
        task.source_datasets,
        task.target_dataset,
    )

    replication_create = ReplicationCreate(
        name=data.name,
        target_dataset=data.target_dataset,
        direction=direction,
        name_regex=name_regex,
        naming_schema=naming_schema,
        also_include_naming_schema=also_include_naming_schema,
        source_datasets=source_datasets,
        transport=task.transport,
        ssh_credentials=task.ssh_credentials.id if task.ssh_credentials else None,
        netcat_active_side=task.netcat_active_side,
        netcat_active_side_listen_address=task.netcat_active_side_listen_address,
        netcat_active_side_port_min=task.netcat_active_side_port_min,
        netcat_active_side_port_max=task.netcat_active_side_port_max,
        netcat_passive_side_connect_address=task.netcat_passive_side_connect_address,
        recursive=task.recursive,
        properties=task.properties,
        replicate=task.replicate,
        compression=task.compression,
        large_block=task.large_block,
        embed=task.embed,
        compressed=task.compressed,
        retries=task.retries,
        retention_policy="NONE",
        auto=False,
        enabled=False,  # Do not run it automatically
    )

    return await context.call2(context.s.replication.do_create, replication_create, app=app)


async def list_datasets(
    context: ServiceContext,
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"],
    ssh_credentials: int | None,
) -> list[str]:
    return await context.middleware.call(  # type: ignore[no-any-return]
        "zettarepl.list_datasets",
        transport,
        ssh_credentials,
    )


async def create_dataset(
    context: ServiceContext,
    dataset: str,
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"],
    ssh_credentials: int | None,
) -> None:
    await context.middleware.call("zettarepl.create_dataset", dataset, transport, ssh_credentials)


async def list_naming_schemas(context: ServiceContext) -> list[str]:
    naming_schemas: list[str] = []
    for snapshottask in await context.call2(context.s.pool.snapshottask.query):
        naming_schemas.append(snapshottask.naming_schema)
    for replication in await context.call2(context.s.replication.query):
        naming_schemas.extend(replication.naming_schema)
        naming_schemas.extend(replication.also_include_naming_schema)
    return sorted(set(naming_schemas))


async def count_eligible_manual_snapshots(
    context: ServiceContext,
    data: ReplicationCountEligibleManualSnapshotsArgs,
) -> ReplicationCountEligibleManualSnapshotsResult:
    return await context.middleware.call(  # type: ignore[no-any-return]
        "zettarepl.count_eligible_manual_snapshots",
        data.model_dump(),
    )


async def target_unmatched_snapshots(
    context: ServiceContext,
    direction: Literal["PUSH", "PULL"],
    source_datasets: list[str],
    target_dataset: str,
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"],
    ssh_credentials: int | None,
) -> dict[str, list[str]]:
    return await context.middleware.call(  # type: ignore[no-any-return]
        "zettarepl.target_unmatched_snapshots",
        direction,
        source_datasets,
        target_dataset,
        transport,
        ssh_credentials,
    )


def new_snapshot_name(naming_schema: str) -> str:
    return datetime.now().strftime(naming_schema)


async def pair(context: ServiceContext, data: ReplicationPairData) -> dict[str, Any]:
    result = await context.call2(
        context.s.keychaincredential.ssh_pair,
        KeychainCredentialSSHPairArg(
            remote_hostname=data.hostname,
            username=data.user or "root",
            public_key=data.public_key,
        ),
    )
    return {
        "ssh_port": result.port,
        "ssh_hostkey": result.host_key,
    }
