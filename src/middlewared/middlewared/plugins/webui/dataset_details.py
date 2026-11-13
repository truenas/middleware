from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import functools
from typing import TYPE_CHECKING, Any

from truenas_os_pyutils.mount import statmount

from middlewared.api.current import (
    QueryOptions,
    WebUIDatasetConsumers,
    WebUIDatasetDetailsEntry,
    WebUIDatasetTasks,
    ZFSResourceQuery,
    ZFSResourceSnapshotCountQuery,
)

from .dataset_consumers import (
    DatasetIndex,
    Resolver,
    match_apps,
    match_containers,
    match_iscsi,
    match_nfs,
    match_nvmet,
    match_push_tasks,
    match_replication_tasks,
    match_smb,
    match_snapshot_tasks,
    match_vms,
    match_webshare,
)

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.service import ServiceContext

    ConsumerFetch = Callable[[ServiceContext, DatasetIndex, Resolver], Mapping[str, Sequence[object]]]
    TaskFetch = Callable[[ServiceContext, DatasetIndex], Mapping[str, int]]

PROPERTIES = (
    "atime",
    "available",
    "casesensitivity",
    "compression",
    "compressratio",
    "dedup",
    "encryption",
    "encryptionroot",
    "keyformat",
    "keystatus",
    "mounted",
    "mountpoint",
    "origin",
    "pbkdf2iters",
    "quota",
    "readonly",
    "refquota",
    "refreservation",
    "reservation",
    "sync",
    "used",
    "usedbychildren",
    "usedbydataset",
    "volsize",
)


def _authorized(app: App, methods: tuple[str, ...]) -> bool:
    credentials = app.authenticated_credentials
    if credentials is None:
        return False
    for method in methods:
        if not credentials.authorize("CALL", method):
            return False
    return True


def _resolver() -> Resolver:
    @functools.cache
    def resolve(path: str) -> str | None:
        try:
            return statmount(path=path, as_dict=False).sb_source
        except (OSError, ValueError):
            return None

    return resolve


def _datastore_rows(context: ServiceContext, table: str, prefix: str | None = None) -> list[dict[str, Any]]:
    # the public task queries join and decrypt credentials this method never reads
    rows: list[dict[str, Any]] = context.middleware.call_sync(
        "datastore.query", table, [], {"prefix": prefix, "relationships": False}
    )
    return rows


def _names(context: ServiceContext, table: str) -> dict[int, str]:
    return {row["id"]: row["name"] for row in _datastore_rows(context, table)}


def _smb(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    shares: list[dict[str, Any]] = context.middleware.call_sync(
        "sharing.smb.query", [], {"extra": {"retrieve_locked_info": False}}
    )
    return match_smb(index, shares, resolve)


def _nfs(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    shares = context.call_sync2(context.s.sharing.nfs.query, [], QueryOptions(extra={"retrieve_locked_info": False}))
    return match_nfs(index, shares, resolve)


def _webshare(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    shares = context.call_sync2(
        context.s.sharing.webshare.query, [], QueryOptions(extra={"retrieve_locked_info": False})
    )
    return match_webshare(index, shares, resolve)


def _iscsi(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    extents: list[dict[str, Any]] = context.middleware.call_sync(
        "iscsi.extent.query", [], {"extra": {"retrieve_locked_info": False}}
    )
    targets: list[dict[str, Any]] = context.middleware.call_sync("iscsi.target.query")
    targetextents: list[dict[str, Any]] = context.middleware.call_sync("iscsi.targetextent.query")
    return match_iscsi(index, extents, targets, targetextents, resolve)


def _nvmet(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    namespaces: list[dict[str, Any]] = context.middleware.call_sync(
        "nvmet.namespace.query", [], {"extra": {"retrieve_locked_info": False}}
    )
    return match_nvmet(index, namespaces, resolve)


def _vms(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    devices = context.call_sync2(context.s.vm.device.query, [["attributes.dtype", "in", ["DISK", "RAW"]]])
    return match_vms(index, devices, _names(context, "vm.vm"), resolve)


def _containers(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    devices = context.call_sync2(context.s.container.device.query, [["attributes.dtype", "=", "FILESYSTEM"]])
    return match_containers(index, devices, _names(context, "container.container"), resolve)


def _apps(context: ServiceContext, index: DatasetIndex, resolve: Resolver) -> Mapping[str, Sequence[object]]:
    return match_apps(index, context.call_sync2(context.s.app.query), resolve)


def _snapshot_tasks(context: ServiceContext, index: DatasetIndex) -> Mapping[str, int]:
    return match_snapshot_tasks(index, _datastore_rows(context, "storage.task", "task_"))


def _replication_tasks(context: ServiceContext, index: DatasetIndex) -> Mapping[str, int]:
    return match_replication_tasks(index, _datastore_rows(context, "storage.replication", "repl_"))


def _cloudsync_tasks(context: ServiceContext, index: DatasetIndex) -> Mapping[str, int]:
    return match_push_tasks(index, _datastore_rows(context, "tasks.cloudsync"))


def _rsync_tasks(context: ServiceContext, index: DatasetIndex) -> Mapping[str, int]:
    return match_push_tasks(index, _datastore_rows(context, "tasks.rsync", "rsync_"))


CONSUMER_SECTIONS: tuple[tuple[str, tuple[str, ...], ConsumerFetch], ...] = (
    ("smb", ("sharing.smb.query",), _smb),
    ("nfs", ("sharing.nfs.query",), _nfs),
    ("webshare", ("sharing.webshare.query",), _webshare),
    ("iscsi", ("iscsi.extent.query", "iscsi.target.query", "iscsi.targetextent.query"), _iscsi),
    ("nvmet", ("nvmet.namespace.query",), _nvmet),
    ("vms", ("vm.query", "vm.device.query"), _vms),
    ("containers", ("container.query", "container.device.query"), _containers),
    ("apps", ("app.query",), _apps),
)
TASK_SECTIONS: tuple[tuple[str, tuple[str, ...], TaskFetch], ...] = (
    ("snapshot", ("pool.snapshottask.query",), _snapshot_tasks),
    ("replication", ("replication.query",), _replication_tasks),
    ("cloudsync", ("cloudsync.query",), _cloudsync_tasks),
    ("rsync", ("rsynctask.query",), _rsync_tasks),
)


def _snapshot_counts(context: ServiceContext, names: list[str]) -> dict[str, int]:
    try:
        counts: dict[str, int] = context.call_sync2(
            context.s.zfs.resource.snapshot.count_impl, ZFSResourceSnapshotCountQuery(recursive=True)
        )
        return counts
    except Exception:
        context.logger.warning("webui.dataset.details: recursive snapshot count failed", exc_info=True)

    counts = {}
    for name in names:
        try:
            counts |= context.call_sync2(
                context.s.zfs.resource.snapshot.count_impl, ZFSResourceSnapshotCountQuery(paths=[name])
            )
        except Exception:
            context.logger.debug("%s: failed to count snapshots", name, exc_info=True)
    return counts


def _entry(
    row: dict[str, Any],
    counts: Mapping[str, int] | None,
    consumers: Mapping[str, Mapping[str, Sequence[object]] | None],
    tasks: Mapping[str, Mapping[str, int] | None],
) -> WebUIDatasetDetailsEntry:
    name = row["name"]
    props = row["properties"]
    consumer_fields: dict[str, Any] = {}
    for key, by_dataset in consumers.items():
        consumer_fields[key] = None if by_dataset is None else by_dataset.get(name, [])
    task_fields: dict[str, Any] = {}
    for key, task_counts in tasks.items():
        task_fields[key] = None if task_counts is None else task_counts.get(name, 0)
    return WebUIDatasetDetailsEntry(
        id=name,
        name=name,
        pool=row["pool"],
        type=row["type"],
        createtxg=row["createtxg"],
        guid=row["guid"],
        properties=props,
        user_properties=row["user_properties"] or {},
        tier=row.get("tier"),
        snapshot_count=None if counts is None else counts.get(name, 0),
        thick_provisioned=(
            bool(props["reservation"]["value"] or props["refreservation"]["value"]) if row["type"] == "VOLUME" else None
        ),
        consumers=WebUIDatasetConsumers(**consumer_fields),
        tasks=WebUIDatasetTasks(**task_fields),
    )


def dataset_details(context: ServiceContext, app: App) -> list[WebUIDatasetDetailsEntry]:
    rows: list[dict[str, Any]] = context.call_sync2(
        context.s.zfs.resource.list_impl,
        ZFSResourceQuery(
            properties=list(PROPERTIES), get_user_properties=True, get_source=True, get_children=True, get_tier=True
        ),
    )
    if not rows:
        return []
    rows.sort(key=lambda row: row["name"].split("/"))
    index = DatasetIndex(rows)
    resolve = _resolver()
    counts = (
        _snapshot_counts(context, [row["name"] for row in rows])
        if _authorized(app, ("zfs.resource.snapshot.count",))
        else None
    )
    consumers: dict[str, Mapping[str, Sequence[object]] | None] = {}
    for key, methods, consumer_fetch in CONSUMER_SECTIONS:
        consumers[key] = consumer_fetch(context, index, resolve) if _authorized(app, methods) else None
    tasks: dict[str, Mapping[str, int] | None] = {}
    for key, methods, task_fetch in TASK_SECTIONS:
        tasks[key] = task_fetch(context, index) if _authorized(app, methods) else None
    return [_entry(row, counts, consumers, tasks) for row in rows]
