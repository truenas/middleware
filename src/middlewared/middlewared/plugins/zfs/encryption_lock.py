from __future__ import annotations

from collections import defaultdict
import contextlib
from datetime import datetime
import errno
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
import uuid

import truenas_os
from truenas_pylibzfs import ZFSError, ZFSException

from middlewared.api.current import (
    ZFSResourceEncryptionLockArgsData,
    ZFSResourceEncryptionUnlockSummaryArgsData,
    ZFSResourceEncryptionUnlockSummaryEntry,
)
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.utils.filesystem import attrs as fs_attrs
from middlewared.utils.filesystem.directory import directory_is_empty

from .encryption import check_key, load_key
from .encryption_info import (
    dataset_can_be_mounted,
    dataset_mountpoint,
    encryption_root_children,
    encryption_roots,
    encryption_state,
)
from .encryption_keys import retrieve_keys_from_file, secret_value, store_key, stored_keys
from .resource_ops import unload_key

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext

__all__ = (
    "assign_supplied_recursive_keys",
    "lock",
    "normalize_unlock_data",
    "start_attachments_on_unlock",
    "unlock",
    "unlock_summary",
)


def normalize_unlock_data(data: dict[str, Any]) -> dict[str, Any]:
    keys: list[dict[str, Any]] = []
    for entry in data.get("keys", []):
        keys.append(
            {
                "path": entry["path"],
                "key": entry.get("key"),
                "passphrase": entry.get("passphrase"),
                "force": entry.get("force", False),
                "recursive": entry.get("recursive", False),
            }
        )
    return {
        "path": data["path"],
        "recursive": data.get("recursive", False),
        "force": data.get("force", False),
        "key_file": data.get("key_file", False),
        "keys": keys,
    }


def assign_supplied_recursive_keys(
    request_keys: list[dict[str, Any]], keys_supplied: dict[str, Any], queried_datasets: list[str]
) -> None:
    by_path: dict[str, dict[str, Any]] = {}
    for entry in request_keys:
        by_path[entry["path"]] = entry
    for name in queried_datasets:
        if name not in keys_supplied:
            for parent_path in Path(name).parents:
                parent = str(parent_path)
                if parent in by_path and by_path[parent]["recursive"]:
                    if parent in keys_supplied:
                        keys_supplied[name] = keys_supplied[parent]
                        break


def lock(context: ServiceContext, tls: Any, data: ZFSResourceEncryptionLockArgsData) -> None:
    path = data.path
    ds = encryption_state(context, tls, path)

    if not ds["encrypted"]:
        raise CallError(f"{path} is not encrypted")
    elif ds["locked"]:
        raise CallError(f"Dataset {path} is already locked")
    elif ds["key_format"] != "passphrase":
        raise CallError("Only datasets which are encrypted with passphrase can be locked")
    elif path != ds["encryption_root"]:
        raise CallError(f"Please lock {ds['encryption_root']}. Only encryption roots can be locked.")

    try:
        # Services consult this while their delegates stop, so they treat the dataset as locked before its key is
        # actually unloaded.
        context.middleware.call_sync("cache.put", "about_to_lock_dataset", path)
        context.call_sync2(context.s.zfs.resource.stop_attachment_delegates, dataset_mountpoint(ds))
        unload_key(tls, path, recursive=ds["type"] != "VOLUME", force_unmount=data.force_unmount)
    finally:
        context.middleware.call_sync("cache.pop", "about_to_lock_dataset")

    if ds["mountpoint"]:
        try:
            fs_attrs.set_zfs_file_attributes_dict(ds["mountpoint"], {"immutable": True})
        except OSError as e:
            # EROFS: the dataset has readonly=on. ENOENT: the mountpoint directory does not exist.
            if e.errno not in (errno.EROFS, errno.ENOENT):
                raise

    context.middleware.call_hook_sync("dataset.post_lock", path)


async def start_attachments_on_unlock(context: ServiceContext, datasets: list[dict[str, Any]]) -> None:
    if not datasets:
        return

    unlocked: list[tuple[dict[str, Any], str | None]] = []
    for dataset in datasets:
        unlocked.append((dataset, dataset_mountpoint(dataset)))
    for delegate in await context.call2(context.s.zfs.resource.attachment_delegates_for_start):
        # The datasets are already unlocked and mounted, so a delegate failure here must not abort
        # the unlock job before its encryption records are persisted
        try:
            await delegate.start_on_unlock(unlocked)
        except Exception:
            context.logger.error("%s: failed to start attachments after unlock", delegate.name, exc_info=True)


def unlock(
    context: ServiceContext, job: Job, tls: Any, data: dict[str, Any], toggle_attachments: bool
) -> dict[str, Any]:
    data = normalize_unlock_data(data)
    path = data["path"]
    verrors = ValidationErrors()
    dataset = encryption_state(context, tls, path)
    keys_supplied: dict[str, Any] = {}

    if data["key_file"]:
        keys_supplied = retrieve_keys_from_file(job)

    for i, entry in enumerate(data["keys"]):
        if entry.get("key") and entry.get("passphrase"):
            verrors.add(
                f"keys.{i}.key",
                f"Must not be specified when passphrase for {entry['path']} is supplied",
            )
        elif not (entry.get("key") or entry.get("passphrase")):
            verrors.add(f"keys.{i}", f"Passphrase or key must be specified for {entry['path']}")

        if not data["force"] and not entry["force"]:
            # Only a dataset that is still locked can collide with what sits at its mount path
            if encryption_state(context, tls, entry["path"])["locked"]:
                if err := dataset_can_be_mounted(entry["path"], os.path.join("/mnt", entry["path"])):
                    verrors.add(f"keys.{i}.force", err)

        keys_supplied[entry["path"]] = entry.get("key") or entry.get("passphrase")

    if "/" in path or not data["recursive"]:
        if not dataset["locked"]:
            verrors.add("path", f"{path} dataset is not locked")
        elif dataset["encryption_root"] != path:
            verrors.add("path", "Only encryption roots can be unlocked")
        elif not stored_keys(context, [["name", "=", path]]) and path not in keys_supplied:
            verrors.add("keys", f"Please specify key for {path}")

    verrors.check()

    locked_datasets = []
    datasets = encryption_roots(context, tls, path.split("/", 1)[0], "locked")
    assign_supplied_recursive_keys(data["keys"], keys_supplied, list(datasets.keys()))

    # Encryption roots end up at the top level, each with a flat "children" list holding only the
    # descendants that share its encryption root, so unlock-then-mount walks [root, child1, child2, ...].
    for name, ds in datasets.items():
        ds_key = keys_supplied.get(name) or ds["encryption_key"]
        if ds["locked"] and path.startswith(f"{name}/"):
            locked_datasets.append(name)
        elif ds["key_format"] == "raw" and ds_key:
            # Raw keys are stored hex encoded
            try:
                ds_key = bytes.fromhex(ds_key)
            except ValueError:
                ds_key = None

        datasets[name] = {"key": ds_key, **ds}

        encryption_children: list[dict[str, Any]] = []
        encryption_root_children(encryption_children, ds["encryption_root"], ds)
        datasets[name]["children"] = encryption_children

    if locked_datasets:
        raise CallError(f"{path} has locked parents {','.join(locked_datasets)} which must be unlocked first")

    failed: defaultdict[str, dict[str, Any]] = defaultdict(lambda: {"error": None, "skipped": []})
    unlocked: list[str] = []
    if data["recursive"]:
        candidates: list[str] = list(datasets)
    else:
        candidates = [path]
    names: list[str] = []
    for n in candidates:
        if n and f"{n}/".startswith(f"{path}/") and datasets[n]["locked"]:
            names.append(n)
    names.sort(key=lambda v: v.count("/"))

    for name_i, name in enumerate(names):
        skip = False
        for i in range(name.count("/") + 1):
            check = name.rsplit("/", i)[0]
            if check in failed:
                failed[check]["skipped"].append(name)
                skip = True
                break

        if skip:
            continue

        if not datasets[name]["key"]:
            failed[name]["error"] = "Missing key"
            continue

        job.set_progress(int(name_i / len(names) * 90 + 0.5), f"Unlocking {name!r}")
        try:
            load_key(tls, name, key=datasets[name]["key"])
        except ZFSException as e:
            if e.code == ZFSError.EZFS_CRYPTOFAILED:
                failed[name]["error"] = "Invalid Key"
            else:
                failed[name]["error"] = str(e)
            continue
        except Exception as e:
            failed[name]["error"] = str(e)
            continue

        # Whatever already occupies a mount path (other than this very dataset) is renamed aside
        # so the dataset can be mounted there.
        to_mount = [datasets[name]] + datasets[name]["children"]
        for ds in to_mount:
            mount_path = os.path.join("/mnt", ds["name"])
            if os.path.exists(mount_path):
                try:
                    sfs = context.middleware.call_sync("filesystem.statfs", mount_path)
                except Exception:
                    pass
                else:
                    if sfs.source == ds["name"]:
                        context.logger.debug(
                            "%s: possible race on mounting dataset. Dataset already mounted. This may "
                            "indicate multiple concurrent API calls impacting dataset locking and mounting",
                            ds["name"],
                        )
                        unlocked.append(ds["name"])
                        continue

                try:
                    fs_attrs.set_zfs_file_attributes_dict(mount_path, {"immutable": False})
                except OSError as e:
                    # EROFS: the dataset can have readonly=on
                    if e.errno != errno.EROFS:
                        raise
                except Exception as e:
                    failed[ds["name"]]["error"] = (
                        f"Dataset mount failed because immutable flag at {mount_path!r} could not be removed: {e}"
                    )
                    # Any deeper paths would fail the same way
                    break

                if not os.path.isdir(mount_path) or not directory_is_empty(mount_path):
                    try:
                        # AT_RENAME_NOREPLACE so a race that materializes the destination name surfaces
                        # as an error instead of silently clobbering whatever appeared.
                        truenas_os.renameat2(
                            mount_path,
                            f"{mount_path}-{str(uuid.uuid4())[:4]}-{datetime.now().isoformat()}",
                            flags=truenas_os.AT_RENAME_NOREPLACE,
                        )
                    except Exception as e:
                        context.logger.error(
                            "%s: failed to move unexpected directory or file from mount path", mount_path, exc_info=True
                        )
                        failed[ds["name"]]["error"] = (
                            f"Dataset mount failed because unexpected file at mount path could not be moved: {e}"
                        )
                        break

            try:
                context.call_sync2(context.s.zfs.resource.mount, ds["name"])
            except Exception as e:
                failed[ds["name"]]["error"] = f"Failed to mount dataset: {e}"
            else:
                unlocked.append(ds["name"])
                try:
                    fs_attrs.set_zfs_file_attributes_dict(mount_path, {"immutable": False})
                except Exception:
                    pass

        # A loaded key with nothing mounted under its encryption root is unloaded again, so the root
        # is left cleanly locked instead of with an orphaned key.
        to_mount_names: set[str] = set()
        for d in to_mount:
            to_mount_names.add(d["name"])
        if not to_mount_names.intersection(unlocked):
            try:
                context.call_sync2(context.s.zfs.resource.unload_key, name)
            except Exception:
                context.logger.warning("%s: failed to unload key after mount failures", name, exc_info=True)

    for failed_ds in failed:
        failed_datasets = {}
        for ds_name in [failed_ds] + failed[failed_ds]["skipped"]:
            mount_path = os.path.join("/mnt", ds_name)
            if os.path.exists(mount_path):
                try:
                    fs_attrs.set_zfs_file_attributes_dict(mount_path, {"immutable": True})
                except OSError as e:
                    # EROFS: the dataset can have readonly=on
                    if e.errno != errno.EROFS:
                        raise
                except Exception as e:
                    failed_datasets[ds_name] = str(e)

        if failed_datasets:
            failed_lines: list[str] = []
            for i, ds_name in enumerate(failed_datasets):
                failed_lines.append(f"{i + 1}) {ds_name!r}: {failed_datasets[ds_name]}")
            failed[failed_ds]["error"] += "\n\nFailed to set immutable flag on following datasets:\n" + "\n".join(
                failed_lines
            )

    if unlocked:
        if toggle_attachments:
            job.set_progress(91, "Handling attachments")
            # Delegates match attachments against the real mountpoint of every dataset that mounted,
            # not against the requested root's subtree.
            unlocked_datasets: dict[str, dict[str, Any]] = {}
            for root in datasets.values():
                for ds in (root, *root["children"]):
                    unlocked_datasets[ds["name"]] = ds
            to_start: list[dict[str, Any]] = []
            for name in unlocked:
                if name in unlocked_datasets:
                    to_start.append(unlocked_datasets[name])
            context.call_sync2(context.s.zfs.resource.encryption.start_attachments_on_unlock, to_start)

        job.set_progress(92, "Updating database")

        def dataset_data(unlocked_dataset: str) -> dict[str, Any]:
            return {
                "encryption_key": keys_supplied.get(unlocked_dataset),
                "name": unlocked_dataset,
                "key_format": datasets[unlocked_dataset]["key_format"].upper(),
            }

        for unlocked_dataset in unlocked:
            if unlocked_dataset not in keys_supplied or unlocked_dataset not in datasets:
                continue

            record = dataset_data(unlocked_dataset)
            store_key(context, record["name"], record["encryption_key"], record["key_format"])

        job.set_progress(94, "Running post-unlock tasks")
        post_unlock_datasets: list[dict[str, Any]] = []
        for ds_name in unlocked:
            if ds_name in datasets:
                post_unlock_datasets.append(dataset_data(ds_name))
        context.middleware.call_hook_sync("dataset.post_unlock", datasets=post_unlock_datasets)

    return {"unlocked": unlocked, "failed": dict(failed)}


def unlock_summary(
    context: ServiceContext, job: Job, tls: Any, data: ZFSResourceEncryptionUnlockSummaryArgsData
) -> list[ZFSResourceEncryptionUnlockSummaryEntry]:
    keys_supplied: dict[str, dict[str, Any]] = {}
    verrors = ValidationErrors()
    if data.key_file:
        for k, v in retrieve_keys_from_file(job).items():
            keys_supplied[k] = {"key": v, "force": False}

    for i, entry in enumerate(data.keys):
        key = secret_value(entry.key)
        passphrase = secret_value(entry.passphrase)
        if key and passphrase:
            verrors.add(f"keys.{i}.key", f"Must not be specified when passphrase for {entry.path} is supplied")
        keys_supplied[entry.path] = {"key": key or passphrase, "force": entry.force}

    verrors.check()
    datasets = encryption_roots(context, tls, data.path, "all")

    results = []
    for name, ds in datasets.items():
        ds_key = keys_supplied.get(name, {}).get("key") or ds["encryption_key"]
        if ds["key_format"] == "raw" and ds_key:
            with contextlib.suppress(ValueError):
                ds_key = bytes.fromhex(ds_key)

        try:
            valid_key = check_key(tls, name, key=ds_key)
        except Exception:
            valid_key = False

        results.append(
            {
                "path": name,
                "key_format": ds["key_format"],
                "key_present_in_database": bool(ds["encryption_key"]),
                "valid_key": valid_key,
                "locked": ds["locked"],
                "unlock_error": None,
                "unlock_successful": False,
            }
        )

    failed = set()
    for ds in sorted(results, key=lambda d: d["path"].count("/")):
        ds_name = ds["path"]
        for i in range(1, ds_name.count("/") + 1):
            check = ds_name.rsplit("/", i)[0]
            if check in failed:
                failed.add(ds_name)
                ds["unlock_error"] = f'Child cannot be unlocked when parent "{check}" is locked'

        ds_locked = ds["locked"]
        if ds_locked and not data.force and not keys_supplied.get(ds_name, {}).get("force"):
            err = dataset_can_be_mounted(ds_name, os.path.join("/mnt", ds_name))
            if ds["unlock_error"] and err:
                ds["unlock_error"] += f" and {err}"
            elif err:
                ds["unlock_error"] = err

        if ds["valid_key"]:
            ds["unlock_successful"] = not bool(ds["unlock_error"])
        elif not ds_locked:
            # An unlock leaves an already unlocked dataset alone, so it succeeds whatever key was given.
            ds["unlock_successful"] = True
        else:
            if ds_name in keys_supplied or ds["key_present_in_database"]:
                if ds["unlock_error"]:
                    ds["unlock_error"] += " and provided key is invalid"
                else:
                    ds["unlock_error"] = "Provided key is invalid"
            elif not ds["unlock_error"]:
                ds["unlock_error"] = "Key not provided"
            failed.add(ds_name)

    entries: list[ZFSResourceEncryptionUnlockSummaryEntry] = []
    for ds in results:
        entries.append(ZFSResourceEncryptionUnlockSummaryEntry(**ds))
    return entries
