from __future__ import annotations

import collections
import errno
from io import BytesIO
import json
import os
import shutil
from typing import TYPE_CHECKING, Any, Literal

from middlewared.api.current import (
    ReplicationEntry,
    ZFSResourceEncryptionExportKeyArgsData,
    ZFSResourceEncryptionExportKeysArgsData,
    ZFSResourceEncryptionExportReplicationKeysArgsData,
    ZFSResourceQuery,
)
from middlewared.plugins.container.utils import CONTAINER_DS_NAME
from middlewared.service_exception import CallError, InstanceNotFound
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID
from middlewared.utils.filesystem.directory import directory_is_empty

from . import resource_query as _query
from .encryption_keys import path_filters, stored_keys
from .utils import INTERNAL_PATHS, get_encryption_info

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext

__all__ = (
    "dataset_can_be_mounted",
    "dataset_mountpoint",
    "encryption_root_children",
    "encryption_root_mapping",
    "encryption_roots",
    "encryption_state",
    "export_key",
    "export_keys",
    "export_replication_keys",
    "replication_keys",
)


def dataset_mountpoint(dataset: dict[str, Any]) -> str | None:
    if dataset["mountpoint"] == "legacy":
        return None

    return dataset["mountpoint"] or os.path.join("/mnt", dataset["name"])


def dataset_can_be_mounted(ds_name: str, ds_mountpoint: str) -> str:
    mount_error_check = ""
    if os.path.isfile(ds_mountpoint):
        mount_error_check = f"A file exists at {ds_mountpoint!r} and {ds_name} cannot be mounted"
    elif os.path.isdir(ds_mountpoint) and not directory_is_empty(ds_mountpoint):
        mount_error_check = f"{ds_mountpoint!r} directory is not empty"
    if mount_error_check:
        mount_error_check += (
            ' (please provide "force" flag to override this error and file/directory '
            "will be renamed once the dataset is unlocked)"
        )
    return mount_error_check


def encryption_root_children(
    child_list_out: list[dict[str, Any]], encryption_root: str, dataset: dict[str, Any]
) -> None:
    for child in dataset["children"]:
        if child["mountpoint"] in ("legacy", "none"):
            # A legacy or unmounted child is mounted by whatever consumer owns it, never forcibly here.
            continue

        if child["encryption_root"] == encryption_root:
            child_list_out.append(child)
            encryption_root_children(child_list_out, encryption_root, child)


def encryption_view(row: dict[str, Any]) -> dict[str, Any]:
    props = row["properties"]
    enc = get_encryption_info(props)
    mountpoint = None
    if row["type"] == "FILESYSTEM":
        mountpoint = props["mountpoint"]["raw"]
    encryption_root = None
    if enc.encrypted:
        encryption_root = props["encryptionroot"]["value"]
    return {
        "name": row["name"],
        "type": row["type"],
        "mountpoint": mountpoint,
        "children": [],
        "encrypted": enc.encrypted,
        "locked": enc.locked,
        "key_loaded": enc.encrypted and not enc.locked,
        "encryption_root": encryption_root,
        "key_format": enc.encryption_type,
    }


def is_internal_dataset_name(path: str) -> bool:
    if path.split("/")[0] in BOOT_POOL_NAME_VALID:
        return True
    for i in (*INTERNAL_PATHS, CONTAINER_DS_NAME):
        if f"/{i}" in path:
            return True
    return False


def encryption_state(context: ServiceContext, tls: Any, path: str) -> dict[str, Any]:
    rows = []
    if not is_internal_dataset_name(path):
        rows = _query.list_impl(context, tls, ZFSResourceQuery(paths=[path], properties=["mountpoint", "encryption"]))
    if not rows:
        raise InstanceNotFound(f"Dataset {path} does not exist")
    return encryption_view(rows[0])


def encryption_roots(
    context: ServiceContext, tls: Any, path: str, state: Literal["locked", "unlocked", "all"]
) -> dict[str, dict[str, Any]]:
    db_results = stored_keys(context, [path_filters(path)])

    datasets: dict[str, dict[str, Any]] = {}
    for row in _query.list_impl(
        context,
        tls,
        ZFSResourceQuery(
            paths=[path], properties=["mountpoint", "encryption"], get_children=True, exclude_internal_paths=False
        ),
    ):
        ds = encryption_view(row)
        datasets[ds["name"]] = ds
        parent_name, sep, _ = ds["name"].rpartition("/")
        if sep and (parent := datasets.get(parent_name)) is not None:
            parent["children"].append(ds)

    result = {}
    for name, ds in datasets.items():
        if name != ds["encryption_root"] or not ds["encrypted"]:
            continue
        if state == "locked" and ds["key_loaded"] or state == "unlocked" and not ds["key_loaded"]:
            continue
        key = None
        if ds["key_format"] != "passphrase":
            key = db_results.get(name)
        result[name] = {"encryption_key": key, **ds}
    return result


def encryption_root_mapping(context: ServiceContext) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = collections.defaultdict(list)
    for dataset in context.call_sync2(
        context.s.zfs.resource.list_impl, ZFSResourceQuery(properties=["encryption"], get_children=True)
    ):
        mapping[dataset["properties"]["encryptionroot"]["value"]].append(dataset["name"])

    return mapping


def replication_keys(
    context: ServiceContext,
    task_or_id: int | ReplicationEntry,
    mapping: dict[str, list[str]] | None = None,
    skip_sync: bool = False,
) -> dict[str, str]:
    if isinstance(task_or_id, int):
        task = context.call_sync2(context.s.replication.get_instance, task_or_id)
    else:
        task = task_or_id
    if task.direction != "PUSH":
        raise CallError("Only push replication tasks are supported.", errno.EINVAL)

    if not skip_sync:
        sync_args: list[list[str]] = []
        for source in task.source_datasets:
            sync_args.append([source])
        context.middleware.call_sync("core.bulk", "zfs.resource.encryption.sync_keys", sync_args).wait_sync()

    source_keys: dict[str, dict[str, str]] = {}
    for source_ds in task.source_datasets:
        rows = context.call_sync2(
            context.s.zfs.resource.list_impl, ZFSResourceQuery(paths=[source_ds], properties=["encryption"])
        )
        if rows and (root := rows[0]["properties"]["encryptionroot"]["value"]) != source_ds:
            filters: list[Any] = ["name", "=", root]
        elif task.recursive:
            filters = path_filters(source_ds)
        else:
            filters = ["name", "=", source_ds]
        source_keys[source_ds] = stored_keys(context, [filters])

    # With no encrypted sources there is nothing to export.
    if not any(source_keys.values()):
        return {}

    result = {}
    include_encryption_root_children = not task.replicate and task.recursive

    source_mapping = context.middleware.call_sync(
        "zettarepl.get_source_target_datasets_mapping", task.source_datasets, task.target_dataset
    )
    if include_encryption_root_children:
        dataset_mapping = mapping or encryption_root_mapping(context)
    else:
        dataset_mapping = {}

    for source_ds in task.source_datasets:
        for ds_name, key in source_keys[source_ds].items():
            if include_encryption_root_children:
                dataset_names = dataset_mapping[ds_name]
            else:
                dataset_names = [ds_name]
            for dataset_name in dataset_names:
                if len(source_ds) <= len(dataset_name):
                    replaced = source_ds
                else:
                    replaced = dataset_name
                result[dataset_name.replace(replaced, source_mapping[source_ds], 1)] = key

    return result


def export_key(context: ServiceContext, job: Job, tls: Any, data: ZFSResourceEncryptionExportKeyArgsData) -> str | None:
    path = data.path
    if data.download:
        job.check_pipe("output")

    encryption_state(context, tls, path)
    keys = stored_keys(context, [["name", "=", path]])
    if path not in keys:
        raise CallError("Specified dataset does not have its own encryption key.", errno.EINVAL)

    if data.download:
        assert job.pipes.output is not None
        job.pipes.output.w.write(json.dumps({path: keys[path]}).encode())
        return None

    return keys[path]


def export_keys(context: ServiceContext, job: Job, tls: Any, data: ZFSResourceEncryptionExportKeysArgsData) -> None:
    path = data.path
    encryption_state(context, tls, path)
    context.call_sync2(context.s.zfs.resource.encryption.sync_keys, path).wait_sync()

    assert job.pipes.output is not None
    with BytesIO(json.dumps(stored_keys(context, [path_filters(path)])).encode()) as f:
        shutil.copyfileobj(f, job.pipes.output.w)


def export_replication_keys(
    context: ServiceContext, job: Job, data: ZFSResourceEncryptionExportReplicationKeysArgsData
) -> None:
    datasets = replication_keys(context, data.id)
    assert job.pipes.output is not None
    job.pipes.output.w.write(json.dumps(datasets).encode())
