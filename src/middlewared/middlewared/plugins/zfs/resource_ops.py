from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

from middlewared.service_exception import ValidationError
from middlewared.utils.filter_list import filter_list

from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathInvalidException,
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSPathNotProvidedException,
)
from .load_unload_impl import unload_key_impl
from .mount_unmount_impl import mount_impl, unmount_impl
from .object_count_impl import estimate_object_count_impl
from .rename_promote_clone_impl import promote_impl, rename_impl
from .zvol_utils import get_zvol_attachments_impl, unlocked_zvols_fast_impl

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


def unlocked_zvols_fast(
    context: ServiceContext,
    filters: list[list[Any]] | None = None,
    options: dict[str, Any] | None = None,
    additional_information: list[str] | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | int:
    if filters is None:
        filters = list()
    if options is None:
        options = dict()
    if additional_information is None:
        additional_information = list()

    att_data = dict()
    if "ATTACHMENT" in additional_information:
        att_data = {"attachments": get_zvol_attachments_impl(context.middleware)}

    return filter_list(
        list(unlocked_zvols_fast_impl(additional_information, att_data).values()),
        filters,
        options,
    )


def estimate_object_count(tls: Any, dataset_name: str) -> int:
    return estimate_object_count_impl(tls, dataset_name)


def promote(tls: Any, current_name: str) -> None:
    schema = "zfs.resource.promote"
    try:
        promote_impl(tls, current_name)
    except ZFSPathInvalidException:
        raise ValidationError(schema, f"{current_name!r} is ineligible for promotion.")
    except ZFSPathNotProvidedException:
        raise ValidationError(schema, "'current_name' key is required")
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def mount(
    tls: Any,
    filesystem: str,
    mountpoint: str | None = None,
    recursive: bool = False,
    mount_options: list[str] | None = None,
    force: bool = False,
    load_encryption_key: bool = False,
) -> None:
    schema = "zfs.resource.mount"
    try:
        mount_impl(tls, filesystem, mountpoint, recursive, mount_options, force, load_encryption_key)
    except ZFSPathNotProvidedException:
        raise ValidationError(schema, "'filesystem' key is required")
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def unmount(
    tls: Any,
    filesystem: str,
    mountpoint: str | None = None,
    recursive: bool = False,
    force: bool = False,
    lazy: bool = False,
    unload_encryption_key: bool = False,
) -> None:
    schema = "zfs.resource.unmount"
    try:
        unmount_impl(tls, filesystem, mountpoint, recursive, force, lazy, unload_encryption_key)
    except ZFSPathNotProvidedException:
        raise ValidationError(schema, "'filesystem' key is required")
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def unload_key(tls: Any, filesystem: str, recursive: bool = False, force_unmount: bool = False) -> None:
    schema = "zfs.resource.unload_key"
    try:
        unload_key_impl(tls, filesystem, recursive, force_unmount)
    except ZFSPathNotProvidedException:
        raise ValidationError(schema, "'filesystem' key is required")
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def rename(
    tls: Any,
    current_name: str,
    new_name: str,
    recursive: bool = False,
    no_unmount: bool = False,
    force_unmount: bool = True,
) -> None:
    schema = "zfs.resource.rename"
    if "@" in current_name:
        raise ValidationError(schema, "Use `zfs.resource.snapshot.rename` to rename snapshots.")
    try:
        rename_impl(tls, current_name, new_name, recursive, no_unmount, force_unmount)
    except ZFSPathNotASnapshotException:
        raise ValidationError(schema, "recursive is only valid for snapshots")
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(schema, e.message, errno.EEXIST)
    except ZFSPathNotProvidedException:
        raise ValidationError(schema, "'current_name' key is required")
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)
