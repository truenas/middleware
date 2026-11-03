from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
import os
from pathlib import PurePosixPath
from typing import Any, Literal

from middlewared.api.current import (
    AppEntry,
    ContainerDeviceEntry,
    ContainerFilesystemDevice,
    SharingNFSEntry,
    SharingWebshareEntry,
    VMDeviceEntry,
    VMDiskDevice,
    VMRAWDevice,
    WebUIDatasetApp,
    WebUIDatasetContainer,
    WebUIDatasetISCSIExtent,
    WebUIDatasetNFSShare,
    WebUIDatasetNVMetNamespace,
    WebUIDatasetSMBShare,
    WebUIDatasetVM,
    WebUIDatasetWebshareShare,
)
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name

Resolver = Callable[[str], str | None]
DatasetType = Literal["FILESYSTEM", "VOLUME"]


class DatasetIndex:
    __slots__ = ("types", "fs_mountpoints", "claims", "unmounted")

    def __init__(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self.types: dict[str, DatasetType] = {}
        self.fs_mountpoints: dict[str, str] = {}
        self.unmounted: dict[str, str] = {}
        claims: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            self.types[row["name"]] = row["type"]
            if row["type"] != "FILESYSTEM":
                continue
            props = row["properties"]
            mountpoint = props["mountpoint"]["raw"]
            if not mountpoint.startswith("/"):
                continue
            self.fs_mountpoints[row["name"]] = mountpoint
            locked = props["encryption"]["raw"] != "off" and props["keystatus"]["raw"] != "available"
            # a locked dataset's path resolves to its parent's placeholder directory, but the consumer belongs to the
            # locked dataset
            if locked or props["mounted"]["raw"] == "yes":
                claims[mountpoint].append(row["name"])
            else:
                self.unmounted[row["name"]] = mountpoint
        self.claims: dict[str, list[str]] = dict(claims)

    def _nearest_claim(self, path: str) -> tuple[str | None, list[str]]:
        for candidate in (path, *map(str, PurePosixPath(path).parents)):
            if (names := self.claims.get(candidate)) is not None:
                return candidate, names
        return None, []

    def filesystem_owner(self, path: str, dataset: str | None, resolve: Resolver) -> str | None:
        path = os.path.normpath(path)
        mountpoint, names = self._nearest_claim(path)
        # the stored dataset is not refreshed when another dataset is later mounted between it and the path
        if len(names) == 1 and (mountpoint == path or names[0] == dataset):
            return names[0]
        if mountpoint != path and dataset is not None and self.unmounted.get(dataset) == path:
            return dataset
        if not path.startswith("/mnt/"):
            return None
        resolved = resolve(path)
        return resolved if resolved is not None and self.types.get(resolved) == "FILESYSTEM" else None

    def volume_owner(self, path: str) -> str | None:
        if not path.startswith("/dev/zvol/"):
            return None
        name = zvol_path_to_name(path)
        return name if self.types.get(name) == "VOLUME" else None


def match_smb(
    index: DatasetIndex, shares: Iterable[Mapping[str, Any]], resolve: Resolver
) -> dict[str, list[WebUIDatasetSMBShare]]:
    result: dict[str, list[WebUIDatasetSMBShare]] = defaultdict(list)
    for share in shares:
        if (owner := index.filesystem_owner(share["path"], share["dataset"], resolve)) is not None:
            result[owner].append(
                WebUIDatasetSMBShare(enabled=share["enabled"], path=share["path"], share_name=share["name"])
            )
    return result


def match_nfs(
    index: DatasetIndex, shares: Iterable[SharingNFSEntry], resolve: Resolver
) -> dict[str, list[WebUIDatasetNFSShare]]:
    result: dict[str, list[WebUIDatasetNFSShare]] = defaultdict(list)
    for share in shares:
        if (owner := index.filesystem_owner(share.path, share.dataset, resolve)) is not None:
            result[owner].append(WebUIDatasetNFSShare(enabled=share.enabled, path=share.path))
    return result


def match_webshare(
    index: DatasetIndex, shares: Iterable[SharingWebshareEntry], resolve: Resolver
) -> dict[str, list[WebUIDatasetWebshareShare]]:
    result: dict[str, list[WebUIDatasetWebshareShare]] = defaultdict(list)
    for share in shares:
        if (owner := index.filesystem_owner(share.path, share.dataset, resolve)) is not None:
            result[owner].append(
                WebUIDatasetWebshareShare(enabled=share.enabled, path=share.path, share_name=share.name)
            )
    return result


def match_iscsi(
    index: DatasetIndex,
    extents: Iterable[Mapping[str, Any]],
    targets: Iterable[Mapping[str, Any]],
    targetextents: Iterable[Mapping[str, Any]],
    resolve: Resolver,
) -> dict[str, list[WebUIDatasetISCSIExtent]]:
    shared = {target["id"] for target in targets if target["groups"]}
    mapped = {te["extent"] for te in targetextents if te["target"] in shared}
    result: dict[str, list[WebUIDatasetISCSIExtent]] = defaultdict(list)
    for extent in extents:
        if extent["id"] not in mapped:
            continue
        if extent["type"] == "DISK":
            path = f"/dev/{extent['path']}"
            owner = index.volume_owner(path)
        elif extent["type"] == "FILE":
            path = extent["path"]
            owner = index.filesystem_owner(path, extent["dataset"], resolve)
        else:
            continue
        if owner is not None:
            result[owner].append(WebUIDatasetISCSIExtent(enabled=extent["enabled"], type=extent["type"], path=path))
    return result


def match_nvmet(
    index: DatasetIndex, namespaces: Iterable[Mapping[str, Any]], resolve: Resolver
) -> dict[str, list[WebUIDatasetNVMetNamespace]]:
    result: dict[str, list[WebUIDatasetNVMetNamespace]] = defaultdict(list)
    for namespace in namespaces:
        if namespace["device_type"] == "ZVOL":
            path = f"/dev/{namespace['device_path']}"
            owner = index.volume_owner(path)
        elif namespace["device_type"] == "FILE":
            path = namespace["device_path"]
            owner = index.filesystem_owner(path, namespace["dataset"], resolve)
        else:
            continue
        if owner is not None:
            result[owner].append(
                WebUIDatasetNVMetNamespace(enabled=namespace["enabled"], type=namespace["device_type"], path=path)
            )
    return result


def match_vms(
    index: DatasetIndex, devices: Iterable[VMDeviceEntry], vm_names: Mapping[int, str], resolve: Resolver
) -> dict[str, list[WebUIDatasetVM]]:
    result: dict[str, list[WebUIDatasetVM]] = defaultdict(list)
    for device in devices:
        if (name := vm_names.get(device.vm)) is None:
            continue
        attrs = device.attributes
        if isinstance(attrs, VMDiskDevice) and attrs.path is not None:
            path = attrs.path
            owner = index.volume_owner(path)
        elif isinstance(attrs, VMRAWDevice):
            path = attrs.path
            owner = index.filesystem_owner(path, None, resolve)
        else:
            continue
        if owner is not None:
            result[owner].append(WebUIDatasetVM(name=name, path=path))
    return result


def match_containers(
    index: DatasetIndex, devices: Iterable[ContainerDeviceEntry], names: Mapping[int, str], resolve: Resolver
) -> dict[str, list[WebUIDatasetContainer]]:
    result: dict[str, list[WebUIDatasetContainer]] = defaultdict(list)
    for device in devices:
        if (name := names.get(device.container)) is None or not isinstance(
            device.attributes, ContainerFilesystemDevice
        ):
            continue
        source = device.attributes.source
        if (owner := index.filesystem_owner(source, None, resolve)) is not None:
            result[owner].append(WebUIDatasetContainer(name=name, path=source))
    return result


def match_apps(index: DatasetIndex, apps: Iterable[AppEntry], resolve: Resolver) -> dict[str, list[WebUIDatasetApp]]:
    result: dict[str, list[WebUIDatasetApp]] = defaultdict(list)
    for app in apps:
        for volume in app.active_workloads.volumes:
            source = volume.source
            if not source.startswith("/mnt/") or source.startswith("/mnt/.ix-"):
                continue
            if (owner := index.filesystem_owner(source, None, resolve)) is not None:
                result[owner].append(WebUIDatasetApp(name=app.name, path=source))
    return result


def match_snapshot_tasks(index: DatasetIndex, tasks: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        if task["dataset"] in index.types:
            counts[task["dataset"]] = counts.get(task["dataset"], 0) + 1
    return counts


def match_replication_tasks(index: DatasetIndex, tasks: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        if task["direction"] != "PUSH":
            continue
        for source in task["source_datasets"]:
            if source in index.types:
                counts[source] = counts.get(source, 0) + 1
    return counts


def match_push_tasks(index: DatasetIndex, tasks: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    paths: dict[PurePosixPath, int] = {}
    for task in tasks:
        if task["direction"] == "PUSH":
            path = PurePosixPath(task["path"])
            paths[path] = paths.get(path, 0) + 1
    result: dict[str, int] = {}
    for name, mountpoint in index.fs_mountpoints.items():
        mp = PurePosixPath(mountpoint)
        count = paths.get(mp, 0)
        for parent in mp.parents:
            count += paths.get(parent, 0)
        result[name] = count
    return result
