from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZFSResourceEntry, ZFSResourceQuery
from middlewared.service_exception import CallError, ValidationError, ValidationErrors

from .create_impl import ZFS_INVALID_INPUT_ERRORS
from .normalization import normalize_asdict_result
from .property_management import DeterminedProperties, build_set_of_zfs_props
from .rules_common import apply_acl_defaults
from .set_rules import (
    SET_READ_PROPERTIES,
    PropertyView,
    SetContext,
    touched_natives,
    validate_request,
    validate_set,
)
from .utils import reject_protected_path, reject_snapshot_path

if TYPE_CHECKING:
    from collections.abc import Iterable

    from middlewared.api.current import ZFSResourceSetArgsData, ZFSResourceSetProperties
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


def _couple_acl_request(data: ZFSResourceSetArgsData) -> tuple[ZFSResourceSetProperties, frozenset[str]]:
    """Setting acltype fills the companions the caller left alone; inheriting it also inherits them."""
    properties = data.properties.model_copy()
    inherit = {*data.inherit}
    apply_acl_defaults(properties, leave=inherit)
    if "acltype" in inherit:
        inherit.update(name for name in ("aclmode", "aclinherit") if getattr(data.properties, name) is None)
    return properties, frozenset(inherit)


def _values(path: str, row: dict[str, Any]) -> PropertyView:
    return PropertyView(path, {name: prop["value"] for name, prop in (row["properties"] or {}).items()})


def _sources(path: str, row: dict[str, Any]) -> PropertyView:
    props = row["properties"] or {}
    return PropertyView(path, {name: (prop["source"] or {}).get("type") for name, prop in props.items()})


def set(context: ServiceContext, data: ZFSResourceSetArgsData) -> ZFSResourceEntry:
    path = data.path
    reject_protected_path(SCHEMA, path)
    verrors = ValidationErrors()
    validate_request(data, verrors)
    verrors.check()

    properties, inherit = _couple_acl_request(data)
    touched = touched_natives(properties, inherit)
    pool_root = "/" not in path
    parent_path = path.rsplit("/", 1)[0]
    fetch_parent = any(":" not in name for name in inherit) and not pool_root

    tier_enabled = None
    if touched & {"special_small_blocks", "dedup"}:
        tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled
    dedup_entitlement = None
    if "dedup" in touched:
        dedup_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.DEDUP)

    paths = [path, parent_path] if fetch_parent else [path]
    rows = {
        row["name"]: row
        for row in context.call_sync2(
            context.s.zfs.resource.list_impl,
            ZFSResourceQuery(
                paths=paths, properties=sorted(SET_READ_PROPERTIES), get_user_properties=False, get_source=True
            ),
        )
    }
    if (target := rows.get(path)) is None:
        raise ValidationError(f"{SCHEMA}.path", f"{path!r} does not exist.", errno.ENOENT)
    parent = None
    if fetch_parent:
        if (parent_row := rows.get(parent_path)) is None:
            raise CallError(f"The parent of {path!r} was removed while its properties were being set.", errno.ENOENT)
        parent = _values(parent_path, parent_row)

    state = SetContext(
        path=path,
        type=target["type"],
        properties=properties,
        user_properties=data.user_properties,
        inherit=inherit,
        current=_values(path, target),
        source=_sources(path, target),
        parent=parent,
        pool_root=pool_root,
        tier_enabled=tier_enabled,
        dedup_entitlement=dedup_entitlement,
    )
    failures = validate_set(context, state, verrors, context.logger)
    verrors.check()
    if failures:
        name, error = failures[0]
        raise CallError(f"{name}: validation failed: {error}")

    if data.dry_run:
        current = target["properties"] or {}
        projected = {name: current[name] for name in sorted(touched) if name in current}
        return ZFSResourceEntry(
            **{**target, "properties": projected or None, "user_properties": None, "children": None}
        )

    return ZFSResourceEntry(
        **context.call_sync2(
            context.s.zfs.resource.set_impl,
            path,
            properties=properties.model_dump(exclude_none=True),
            user_properties=data.user_properties,
            inherit=sorted(inherit),
        )
    )
