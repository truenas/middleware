from __future__ import annotations

import typing

from middlewared.api.current import ZFSResourceQuery, ZFSResourceSnapshotCreateQuery
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import CallError, ServiceContext, ValidationErrors

from .utils import applications_ds_name

if typing.TYPE_CHECKING:
    from middlewared.job import Job


async def backup_to_pool(context: ServiceContext, job: Job, target_pool: str) -> None:
    verrors = ValidationErrors()
    docker_config = await context.call2(context.s.docker.config)
    if docker_config.pool is None:
        verrors.add("pool", "Docker is not configured to use a pool")
    if target_pool == docker_config.pool:
        verrors.add("target_pool", "Target pool cannot be the same as the current Docker pool")

    verrors.check()

    target_root_ds = await context.call2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[target_pool], properties=["encryption"])
    )
    if not target_root_ds:
        verrors.add("target_pool", "Target pool does not exist")
    elif get_encryption_info(target_root_ds[0]["properties"]).encrypted:
        # This is not allowed because destination root if encrypted means that docker datasets would be
        # not encrypted and by design we don't allow this to happen to keep it simple / straight forward.
        # https://github.com/truenas/zettarepl/blob/52d3b7a00fa4630c3428ae4e70bc33cf41a6d768/zettarepl/
        # replication/run.py#L319
        verrors.add("target_pool", f"Backup to an encrypted pool {target_pool!r} is not allowed")

    verrors.check()

    assert docker_config.pool is not None
    job.set_progress(10, "Initial validation has been completed, stopping docker service")
    await (await context.middleware.call("service.control", "STOP", "docker")).wait(raise_error=True)
    job.set_progress(30, "Snapshotting apps dataset")
    schema = f"ix-apps-{docker_config.pool}-to-{target_pool}-backup-%Y-%m-%d_%H-%M-%S"
    try:
        # Resolve naming schema to get snapshot name
        snap_name = await context.middleware.call(
            "replication.new_snapshot_name", schema
        )
        await context.call2(context.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
            dataset=applications_ds_name(docker_config.pool),
            name=snap_name,
            recursive=True,
            bypass=True,
        ))
    finally:
        # We do this in try/finally block to ensure that docker service is started back
        await (await context.middleware.call("service.control", "START", "docker")).wait(raise_error=True)

    job.set_progress(45, "Incrementally replicating apps dataset")

    try:
        await incrementally_replicate_apps_dataset(context, docker_config.pool, target_pool, schema)
    except Exception:
        job.set_progress(90, "Failed to incrementally replicate apps dataset")
        raise
    else:
        job.set_progress(100, "Successfully incrementally replicated apps dataset")


async def incrementally_replicate_apps_dataset(
    context: ServiceContext, source_pool: str, target_pool: str, schema: str
) -> None:
    old_ds = applications_ds_name(source_pool)
    new_ds = applications_ds_name(target_pool)
    replication_job = await context.middleware.call(
        "replication.run_onetime", {
            "direction": "PUSH",
            "transport": "LOCAL",
            "source_datasets": [old_ds],
            "target_dataset": new_ds,
            "recursive": True,
            "also_include_naming_schema": [schema],
            "retention_policy": "SOURCE",
            "replicate": True,
            "readonly": "IGNORE",
            "exclude_mountpoint_property": True,
            "mount": False,
        }
    )
    await replication_job.wait()
    if replication_job.error:
        raise CallError(f"Failed to migrate {old_ds} to {new_ds}: {replication_job.error}")
