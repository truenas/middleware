from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from middlewared.api.current import (
    ZFSResourceEncryptionChangeKeyArgsData,
    ZFSResourceEncryptionInheritArgsData,
    ZFSResourceQuery,
)
from middlewared.service_exception import CallError, ValidationErrors

from . import resource_query as _query
from .encryption import EncryptionProperties, change_encryption_root
from .encryption import change_key as zfs_change_key
from .encryption_info import encryption_state
from .encryption_keys import read_hex_key_from_pipe, resolve_key_options, store_key
from .utils import ancestor_chain, secret_value

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext

__all__ = ("change_key", "inherit")

KEY_CHILDREN_ERROR = (
    "{path} has children which are encrypted with a key. It is not allowed to have encrypted "
    "roots which are encrypted with a key as children for passphrase encrypted datasets."
)


def has_key_encrypted_child_roots(context: ServiceContext, tls: Any, path: str) -> bool:
    for r in _query.list_impl(
        context, tls, ZFSResourceQuery(paths=[path], properties=["encryption"], get_children=True)
    ):
        if (
            r["name"] != path
            and r["properties"]["encryptionroot"]["value"] == r["name"]
            and r["properties"]["keyformat"]["raw"] != "passphrase"
        ):
            return True
    return False


def change_key(context: ServiceContext, job: Job, tls: Any, data: ZFSResourceEncryptionChangeKeyArgsData) -> None:
    path = data.path
    key = secret_value(data.key)
    passphrase = secret_value(data.passphrase)
    ds = encryption_state(context, tls, path)
    verrors = ValidationErrors()
    if not ds["encrypted"]:
        verrors.add("path", "Dataset is not encrypted")
    elif ds["locked"]:
        verrors.add("path", "Dataset must be unlocked before key can be changed")

    if not verrors:
        if passphrase:
            if data.generate_key or key:
                verrors.add("key", f"Must not be specified when passphrase for {path} is supplied.")
            elif has_key_encrypted_child_roots(context, tls, path):
                verrors.add("passphrase", KEY_CHILDREN_ERROR.format(path=path))
            elif path == context.middleware.call_sync("systemdataset.config")["pool"]:
                verrors.add(
                    "path",
                    f"{path} contains the system dataset. Please move the system dataset to a "
                    "different pool before changing key_format.",
                )
        else:
            if not data.generate_key and not key:
                for k in ("key", "passphrase", "generate_key"):
                    verrors.add(k, "Either Key or passphrase must be provided.")
            elif path.count("/"):
                for r in _query.list_impl(
                    context, tls, ZFSResourceQuery(paths=ancestor_chain(path), properties=["encryption"])
                ):
                    if r["properties"]["keyformat"]["raw"] == "passphrase":
                        verrors.add(
                            "key",
                            f"{path} has parent(s) which are encrypted with a passphrase. It is not allowed to have "
                            "encrypted roots which are encrypted with a key as children for passphrase encrypted "
                            "datasets.",
                        )
                        break

    verrors.check()

    key_from_file = None
    if data.key_file and not (key or data.generate_key or passphrase):
        key_from_file = read_hex_key_from_pipe(job, verrors)

    encryption_dict = resolve_key_options(
        verrors,
        {
            "enabled": True,
            "passphrase": passphrase,
            "generate_key": data.generate_key,
            "key_file": data.key_file,
            "pbkdf2iters": data.pbkdf2iters,
            "key": key,
        },
        "",
        key_from_file,
    )
    verrors.check()

    new_key = encryption_dict.pop("key")
    zfs_change_key(tls, path, cast(EncryptionProperties, encryption_dict), new_key)

    if passphrase:
        key_format = "passphrase"
    else:
        key_format = "hex"
    store_key(context, path, new_key, key_format)
    if passphrase and ds["key_format"] != "passphrase":
        context.call_sync2(context.s.zfs.resource.encryption.sync_keys, path)

    context.middleware.call_hook_sync(
        "dataset.change_key",
        {
            "encryption_key": new_key,
            "key_format": key_format.upper(),
            "name": path,
            "old_key_format": ds["key_format"].upper(),
        },
    )


def inherit(context: ServiceContext, tls: Any, data: ZFSResourceEncryptionInheritArgsData) -> None:
    path = data.path
    ds = encryption_state(context, tls, path)
    if not ds["encrypted"]:
        raise CallError(f"Dataset {path} is not encrypted")
    elif ds["encryption_root"] != path:
        raise CallError(f"Dataset {path} is not an encryption root")
    elif ds["locked"]:
        raise CallError("Dataset must be unlocked to perform this operation")
    elif "/" not in path:
        raise CallError("Root datasets do not have a parent and cannot inherit encryption settings")

    parent = encryption_state(context, tls, path.rsplit("/", 1)[0])
    if not parent["encrypted"]:
        raise CallError("This operation requires the parent dataset to be encrypted")

    parent_root = encryption_state(context, tls, parent["encryption_root"])
    if parent_root["key_format"] == "passphrase" and has_key_encrypted_child_roots(context, tls, path):
        raise CallError(KEY_CHILDREN_ERROR.format(path=path))

    change_encryption_root(tls, path)
    context.call_sync2(context.s.zfs.resource.encryption.sync_keys, path)
    context.middleware.call_hook_sync("dataset.inherit_parent_encryption_root", path)
