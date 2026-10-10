from __future__ import annotations

import contextlib
import json
import re
from typing import TYPE_CHECKING, Any

from middlewared.api.current import ZFSResourceQuery
from middlewared.service_exception import CallError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import secrets
from middlewared.utils.filter_list import filter_list
from middlewared.utils.size import MB

from . import resource_query as _query
from .encryption import check_key

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext

__all__ = (
    "delete_keys",
    "path_filters",
    "read_hex_key_from_pipe",
    "resolve_key_options",
    "retrieve_keys_from_file",
    "store_key",
    "stored_keys",
    "sync_keys",
)

DATASET_DATABASE_MODEL_NAME = "storage.encrypteddataset"
HEX_KEY_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


class EncryptedDatasetModel(sa.Model):
    __tablename__ = "storage_encrypteddataset"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


def path_filters(path: str) -> list[Any]:
    return ["OR", [["name", "=", path], ["name", "^", f"{path}/"]]]


def store_key(context: ServiceContext, name: str, encryption_key: str | None, key_format: str | None) -> int | None:
    if not encryption_key or not key_format or key_format == "passphrase":
        # Passphrases are only known to the user and are never persisted.
        return None

    data = {"name": name, "encryption_key": encryption_key}
    rows = context.middleware.call_sync("datastore.query", DATASET_DATABASE_MODEL_NAME, [["name", "=", name]])
    if rows:
        pk: int = rows[0]["id"]
        context.middleware.call_sync("datastore.update", DATASET_DATABASE_MODEL_NAME, pk, data)
    else:
        pk = context.middleware.call_sync("datastore.insert", DATASET_DATABASE_MODEL_NAME, data)

    kmip_config = context.call_sync2(context.s.kmip.config)
    if kmip_config.enabled and kmip_config.manage_zfs_keys:
        context.call_sync2(context.s.kmip.sync_zfs_keys, [pk])

    return pk


def delete_keys(context: ServiceContext, filters: list[Any]) -> None:
    for ds in context.middleware.call_sync("datastore.query", DATASET_DATABASE_MODEL_NAME, filters):
        if ds["kmip_uid"]:
            context.call_sync2(context.s.kmip.reset_zfs_key, ds["name"], ds["kmip_uid"], background=True)
        context.middleware.call_sync("datastore.delete", DATASET_DATABASE_MODEL_NAME, ds["id"])


def stored_keys(context: ServiceContext, filters: list[Any]) -> dict[str, str]:
    # A key in the database is taken as correct. Otherwise the KMIP server's in-memory copy is used, if it has
    # one; a key missing from both becomes retrievable again once the user syncs KMIP keys.
    datasets = filter_list(context.middleware.call_sync("datastore.query", DATASET_DATABASE_MODEL_NAME), filters)
    zfs_keys = context.call_sync2(context.s.kmip.retrieve_zfs_keys)
    keys: dict[str, str] = {}
    for ds in datasets:
        if ds["encryption_key"]:
            keys[ds["name"]] = ds["encryption_key"]
        elif ds["name"] in zfs_keys:
            keys[ds["name"]] = zfs_keys[ds["name"]]
    return keys


def sync_keys(context: ServiceContext, tls: Any, name: str | None = None) -> None:
    if not context.middleware.call_sync("failover.is_single_master_node"):
        return
    filters: list[Any] = []
    if name:
        filters.append(path_filters(name))

    # A configured pool that failed to import (e.g. booted with its disks missing) must keep its keys.
    pool_names: set[str] = set()
    for pool in context.middleware.call_sync("pool.query"):
        pool_names.add(pool["name"])
    ds_names: set[str] = set()
    for row in _query.list_impl(context, tls, ZFSResourceQuery(properties=None)):
        ds_names.add(row["name"])
    for root_ds in pool_names - ds_names:
        filters.extend([["name", "!=", root_ds], ["name", "!^", f"{root_ds}/"]])

    db_datasets = stored_keys(context, filters)
    paths: list[str] = []
    if name:
        paths.append(name)
    encrypted_roots: dict[str, dict[str, Any]] = {}
    for r in _query.list_impl(
        context, tls, ZFSResourceQuery(paths=paths, properties=["encryption"], get_children=True)
    ):
        if r["properties"]["encryptionroot"]["value"] == r["name"]:
            encrypted_roots[r["name"]] = r

    to_remove = []
    try:
        for ds_name, db_key in db_datasets.items():
            key: str | bytes = db_key
            ds = encrypted_roots.get(ds_name)
            if ds and ds["properties"]["keyformat"]["raw"] == "raw" and key:
                with contextlib.suppress(ValueError):
                    key = bytes.fromhex(db_key)

            try:
                should_remove = not check_key(tls, ds_name, key=key)
            except Exception:
                should_remove = True

            if should_remove:
                to_remove.append(ds_name)

    except Exception:
        context.logger.error("%s: failed to sync stored encryption keys", name or "all datasets", exc_info=True)
        return

    delete_keys(context, [["name", "in", to_remove]])


def retrieve_keys_from_file(job: Job) -> dict[str, str]:
    job.check_pipe("input")
    try:
        data = json.loads(job.pipes.input.r.read(10 * MB))
    except json.JSONDecodeError:
        raise CallError("Input file must be a valid JSON file")

    if not isinstance(data, dict):
        raise CallError("Please specify correct format for input file")
    for v in data.values():
        if not isinstance(v, str):
            raise CallError("Please specify correct format for input file")

    return data


def _attribute(schema: str, name: str) -> str:
    if schema:
        return f"{schema}.{name}"
    return name


def read_hex_key_from_pipe(job: Job, verrors: ValidationErrors) -> str | None:
    job.check_pipe("input")
    key: str = job.pipes.input.r.read(64).decode("ascii", errors="replace")
    if not HEX_KEY_PATTERN.fullmatch(key):
        verrors.add("key_file", "Please specify a valid key")
        return None
    return key.lower()


def resolve_key_options(
    verrors: ValidationErrors, data: dict[str, Any], schema: str, key_from_file: str | None = None
) -> dict[str, Any]:
    opts: dict[str, Any] = {}
    if not data["enabled"]:
        return opts

    key = data["key"]
    passphrase = data["passphrase"]
    passphrase_key_format = bool(passphrase)

    if passphrase_key_format:
        for f in ("key", "key_file", "generate_key"):
            if data[f]:
                verrors.add(_attribute(schema, f), "Must be disabled when dataset is to be encrypted with passphrase.")
    else:
        provided_opts: list[str] = []
        for k in ("key", "key_file", "generate_key"):
            if data[k]:
                provided_opts.append(k)
        if not provided_opts:
            verrors.add(
                _attribute(schema, "key"),
                "Please provide a key or select generate_key to automatically generate "
                "a key when passphrase is not provided.",
            )
        elif len(provided_opts) > 1:
            for k in provided_opts:
                verrors.add(_attribute(schema, k), f"Only one of {', '.join(provided_opts)} must be provided.")

    if not verrors:
        key = key or passphrase
        if data["generate_key"]:
            key = secrets.token_hex(32)
        elif not key and key_from_file is not None:
            key = key_from_file

        if passphrase_key_format:
            keyformat = "passphrase"
        else:
            keyformat = "hex"
        opts = {"keyformat": keyformat, "keylocation": "prompt", "key": key}
        if passphrase_key_format:
            opts["pbkdf2iters"] = data["pbkdf2iters"]
    return opts
