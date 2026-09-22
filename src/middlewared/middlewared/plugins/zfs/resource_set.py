from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZFSResourceEntry, ZFSResourceQuery
from middlewared.service_exception import CallError, ValidationError

from .create_impl import ZFS_INVALID_INPUT_ERRORS
from .normalization import normalize_asdict_result
from .property_management import DeterminedProperties, build_set_of_zfs_props
from .set_rules import (
    SetContext,
    check_acl_combination,
    check_dedup_entitlement,
    check_dedup_tiering,
    check_has_work,
    check_inherit_names,
    check_path_shape,
    check_resource_exists,
    check_set_inherit_conflict,
    check_tier_managed_ssb,
    check_user_property_names,
    check_volsize_not_shrunk,
    resolve_set_request,
)
from .utils import reject_protected_path, reject_snapshot_path

if TYPE_CHECKING:
    from collections.abc import Iterable

    from middlewared.api.current import ZFSResourceSetArgsData
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.set"


_ZFS_ERRNO = {
    truenas_pylibzfs.ZFSError.EZFS_BUSY: errno.EBUSY,
    truenas_pylibzfs.ZFSError.EZFS_IO: errno.EIO,
    truenas_pylibzfs.ZFSError.EZFS_NOSPC: errno.ENOSPC,
    truenas_pylibzfs.ZFSError.EZFS_PERM: errno.EPERM,
}


def _read(ds: Any, natives: list[str], user: bool) -> dict[str, Any]:
    row: dict[str, Any] = ds.asdict(
        properties=build_set_of_zfs_props(ds.type, DeterminedProperties(), natives or None),
        get_user_properties=user,
        get_source=False,
    )
    return row


def _values_on_disk(ds: Any, natives: list[str], user_names: list[str]) -> str:
    if ds is None:
        return ""
    try:
        ds.refresh_properties()
        row = _read(ds, natives, bool(user_names))
    except truenas_pylibzfs.ZFSException:
        return ""
    props = row["properties"] or {}
    user_props = row["user_properties"] or {}
    values = [f"{name}={props.get(name, {}).get('value')}" for name in natives]
    values.extend(f"{name}={user_props.get(name)}" for name in user_names)
    return f" Values now on disk: {', '.join(values)}."


def _phase_error(
    ds: Any,
    path: str,
    e: Any,
    attribute: str,
    invalid_message: str,
    other_message: str,
    natives: list[str],
    user_names: list[str],
) -> CallError | ValidationError:
    if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
        return CallError(f"{path!r} was removed while its properties were being set.", errno.ENOENT)
    values = _values_on_disk(ds, natives, user_names)
    if e.code in ZFS_INVALID_INPUT_ERRORS:
        return ValidationError(attribute, invalid_message + values, errno.EINVAL)
    return CallError(other_message + values, _ZFS_ERRNO.get(e.code, errno.EFAULT))


def set_impl(
    tls: Any,
    path: str,
    properties: dict[str, Any] | None = None,
    user_properties: dict[str, str] | None = None,
    inherit: Iterable[str] | None = None,
    bypass: bool = False,
) -> dict[str, Any]:
    reject_snapshot_path(SCHEMA, path)
    reject_protected_path(SCHEMA, path, bypass)
    # libzfs refuses a numeric 0 for quota and refquota and requires the word none; the other limits accept 0
    properties = {
        name: "none" if name in ("quota", "refquota") and value in (0, "0", "none") else value
        for name, value in (properties or {}).items()
    }
    user_properties = dict(user_properties or {})
    inherit = list(inherit or ())
    natives = sorted(properties.keys() | {name for name in inherit if ":" not in name})
    user_names = sorted(user_properties.keys() | {name for name in inherit if ":" in name})

    native_attribute = f"{SCHEMA}.properties"
    if len(properties) == 1:
        native_attribute = f"{native_attribute}.{next(iter(properties))}"
    try:
        ds = tls.lzh.open_resource(name=path)
    except truenas_pylibzfs.ZFSException as e:
        raise _phase_error(
            None, path, e, native_attribute, e.err_str, f"Failed to set properties on {path!r}: {e}", [], []
        ) from e
    try:
        if properties:
            try:
                ds.set_properties(properties=properties)
            except truenas_pylibzfs.ZFSException as e:
                raise _phase_error(
                    ds,
                    path,
                    e,
                    native_attribute,
                    e.err_str,
                    f"Failed to set properties on {path!r}: {e}",
                    natives,
                    user_names,
                ) from e
        if user_properties:
            try:
                ds.set_user_properties(user_properties=user_properties)
            except truenas_pylibzfs.ZFSException as e:
                raise _phase_error(ds, path, e, f"{SCHEMA}.user_properties", f"{e}", f"{e}", natives, user_names) from e
        for name in inherit:
            try:
                ds.inherit_property(property=name)
            except truenas_pylibzfs.ZFSException as e:
                message = f"Failed to inherit {name!r} on {path!r}: {e}"
                raise _phase_error(
                    ds, path, e, f"{SCHEMA}.inherit.{name}", message, message, natives, user_names
                ) from e
    except ValueError as e:
        raise CallError(
            f"ZFS rejected a property name or value for {path!r} that middleware accepted: {e}", errno.EINVAL
        ) from e

    info = normalize_asdict_result(_read(ds, natives, bool(user_names)), normalize_source=False)
    info["children"] = None
    return info


def set(context: ServiceContext, data: ZFSResourceSetArgsData) -> ZFSResourceEntry:
    path = data.path
    properties, inherit = resolve_set_request(data)
    ctx = SetContext(properties=properties, inherit=inherit)

    check_path_shape(data, ctx)
    reject_protected_path(SCHEMA, path)
    check_has_work(data, ctx)
    check_set_inherit_conflict(data, ctx)
    check_inherit_names(data, ctx)
    check_user_property_names(data, ctx)

    ctx.tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled
    if ctx.tier_enabled:
        check_tier_managed_ssb(data, ctx)

    # any value other than off (on, verify, a checksum) enables dedup.
    # The entitlement is settled before the resource is read so an
    # unlicensed request fails without further work.
    dedup_requested = str(properties.dedup or "off").lower() != "off"
    if dedup_requested:
        ctx.dedup_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.DEDUP)
        check_dedup_entitlement(data, ctx)

    # one read serves existence, the type and every rule below.
    acl_requested = properties.acltype is not None or properties.aclmode is not None
    wanted = []
    if properties.volsize is not None:
        wanted.append("volsize")
    if acl_requested:
        wanted.extend(["acltype", "aclmode"])
    if dedup_requested and ctx.tier_enabled and properties.special_small_blocks is None:
        wanted.append("special_small_blocks")
    rows = context.call_sync2(
        context.s.zfs.resource.list_impl,
        ZFSResourceQuery(paths=[path], properties=wanted or None),
    )
    ctx.current = rows[0] if rows else None
    check_resource_exists(data, ctx)
    assert ctx.current is not None

    if ctx.current["type"] == "VOLUME":
        if properties.volsize is not None:
            check_volsize_not_shrunk(data, ctx)
    else:
        if acl_requested:
            check_acl_combination(data, ctx)
        if dedup_requested and ctx.tier_enabled:
            check_dedup_tiering(context, data, ctx)

    props = properties.model_dump(exclude_none=True)
    return ZFSResourceEntry(
        **context.call_sync2(
            context.s.zfs.resource.set_impl,
            path,
            properties=props,
            user_properties=data.user_properties,
            inherit=sorted(inherit),
        )
    )
