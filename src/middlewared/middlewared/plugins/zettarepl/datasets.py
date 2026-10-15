from __future__ import annotations

import errno
import re
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal

from zettarepl.dataset.create import create_dataset as zettarepl_create_dataset
from zettarepl.dataset.list import list_datasets as zettarepl_list_datasets
from zettarepl.replication.task.dataset import get_source_dataset_base, get_target_dataset
from zettarepl.replication.task.name_pattern import compile_name_regex
from zettarepl.snapshot.list import group_snapshots_by_datasets, multilist_snapshots
from zettarepl.snapshot.name import parse_snapshots_names_with_multiple_schemas
from zettarepl.transport.local import LocalShell

from middlewared.api.current import (
    ReplicationCountEligibleManualSnapshotsArgs,
    ReplicationEligibleManualSnapshots,
)
from middlewared.service_exception import CallError

from .transport import Transport, get_zettarepl_shell, handle_ssh_exceptions

if TYPE_CHECKING:
    from zettarepl.transport.interface import Shell

    from middlewared.service import ServiceContext

INVALID_DATASETS = (re.compile(r"boot-pool($|/)"), re.compile(r"freenas-boot($|/)"), re.compile(r"[^/]+/\.system($|/)"))


def fake_task(source_datasets: list[str], target_dataset: str) -> Any:
    """A stand-in for the `ReplicationTask` that the dataset mapping helpers read two attributes of."""
    return SimpleNamespace(source_datasets=source_datasets, target_dataset=target_dataset)


async def list_datasets(
    context: ServiceContext,
    transport: Transport,
    ssh_credentials: int | None = None,
) -> list[str]:
    async with handle_ssh_exceptions():
        async with get_zettarepl_shell(context, transport, ssh_credentials) as shell:
            datasets = await context.middleware.run_in_thread(zettarepl_list_datasets, shell)

    return [ds for ds in datasets if not any(r.match(ds) for r in INVALID_DATASETS)]


async def create_dataset(
    context: ServiceContext,
    dataset: str,
    transport: Transport,
    ssh_credentials: int | None = None,
) -> None:
    async with handle_ssh_exceptions():
        async with get_zettarepl_shell(context, transport, ssh_credentials) as shell:
            await context.middleware.run_in_thread(zettarepl_create_dataset, shell, dataset)


async def count_eligible_manual_snapshots(
    context: ServiceContext,
    data: ReplicationCountEligibleManualSnapshotsArgs,
) -> ReplicationEligibleManualSnapshots:
    if data.naming_schema and data.name_regex:
        raise CallError("`naming_schema` and `name_regex` cannot be used simultaneously", errno.EINVAL)

    async with handle_ssh_exceptions():
        async with get_zettarepl_shell(context, data.transport, data.ssh_credentials) as shell:
            snapshots = await context.middleware.run_in_thread(
                multilist_snapshots, shell, [(dataset, False) for dataset in data.datasets]
            )

    if data.naming_schema:
        parsed = parse_snapshots_names_with_multiple_schemas([s.name for s in snapshots], data.naming_schema)
    elif data.name_regex:
        try:
            name_pattern = compile_name_regex(data.name_regex)
        except Exception as e:
            raise CallError(f"Invalid `name_regex`: {e}")

        parsed = [s.name for s in snapshots if name_pattern.match(s.name)]
    else:
        raise CallError("Either `naming_schema` or `name_regex` must be specified", errno.EINVAL)

    return ReplicationEligibleManualSnapshots(
        total=len(snapshots),
        eligible=len(parsed),
    )


def get_source_target_datasets_mapping(source_datasets: list[str], target_dataset: str) -> dict[str, str]:
    fake_replication_task = fake_task(source_datasets, target_dataset)
    return {
        source_dataset: get_target_dataset(fake_replication_task, source_dataset) for source_dataset in source_datasets
    }


def reverse_source_target_datasets(source_datasets: list[str], target_dataset: str) -> tuple[list[str], str]:
    if len(source_datasets) == 1:
        return [target_dataset], source_datasets[0]

    replication_task = fake_task(source_datasets, target_dataset)
    return (
        [get_target_dataset(replication_task, source_dataset) for source_dataset in source_datasets],
        get_source_dataset_base(replication_task),
    )


async def target_unmatched_snapshots(
    context: ServiceContext,
    direction: Literal["PUSH", "PULL"],
    source_datasets: list[str],
    target_dataset: str,
    transport: Transport,
    ssh_credentials: int | None = None,
) -> dict[str, list[str]]:
    datasets = get_source_target_datasets_mapping(source_datasets, target_dataset)

    try:
        local_shell: Shell = LocalShell()
        async with get_zettarepl_shell(context, transport, ssh_credentials) as remote_shell:
            if direction == "PUSH":
                source_shell = local_shell
                target_shell = remote_shell
            else:
                source_shell = remote_shell
                target_shell = local_shell

            target_datasets = set(await context.middleware.run_in_thread(zettarepl_list_datasets, target_shell))
            datasets = {source: target for source, target in datasets.items() if target in target_datasets}

            source_snapshots = group_snapshots_by_datasets(
                await context.middleware.run_in_thread(
                    multilist_snapshots, source_shell, [(dataset, False) for dataset in datasets.keys()]
                )
            )
            target_snapshots = group_snapshots_by_datasets(
                await context.middleware.run_in_thread(
                    multilist_snapshots, target_shell, [(dataset, False) for dataset in datasets.values()]
                )
            )
    except Exception as e:
        raise CallError(repr(e))

    errors = {}
    for source, target in datasets.items():
        unmatched_snapshots = list(set(target_snapshots.get(target, [])) - set(source_snapshots.get(source, [])))
        if unmatched_snapshots:
            errors[target] = unmatched_snapshots

    return errors
