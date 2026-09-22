from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

from middlewared.api.current import ZFSResourcePromoteArgsData, ZFSResourceRenameArgsData
from middlewared.service_exception import ValidationError
from middlewared.utils.filter_list import filter_list

from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathInvalidException,
    ZFSPathNotFoundException,
    ZFSPathNotProvidedException,
)
from .load_unload_impl import unload_key_impl
from .mount_unmount_impl import mount_impl, unmount_impl
from .rename_promote_clone_impl import promote_impl as _raw_promote
from .rename_promote_clone_impl import rename_impl as _raw_rename
from .utils import reject_protected_path
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


def promote_impl(tls: Any, data: ZFSResourcePromoteArgsData) -> None:
    schema = "zfs.resource.promote"
    reject_protected_path(schema, data.path, data.bypass)
    try:
        _raw_promote(tls, data.path)
    except ZFSPathInvalidException as e:
        raise ValidationError(schema, e.message, errno.EINVAL)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def promote(context: ServiceContext, data: ZFSResourcePromoteArgsData) -> None:
    context.call_sync2(context.s.zfs.resource.promote_impl, data)


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


def rename_impl(tls: Any, data: ZFSResourceRenameArgsData) -> None:
    schema = "zfs.resource.rename"
    reject_protected_path(schema, data.current_name, data.bypass)
    reject_protected_path(schema, data.new_name, data.bypass)
    try:
        _raw_rename(tls, data.current_name, data.new_name, False, data.no_unmount, data.force_unmount)
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(schema, e.message, errno.EEXIST)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def rename(context: ServiceContext, data: ZFSResourceRenameArgsData) -> None:
    context.call_sync2(context.s.zfs.resource.rename_impl, data)
