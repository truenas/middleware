"""Validation rules for zfs.resource.set, in the shape create_rules describes. Shared checks come from
create_rules as `reject_*` functions taking plain values; "effective" here is read from the resource being
updated rather than from an ancestor.
"""

from __future__ import annotations

import dataclasses
import errno
import typing

from middlewared.api.current import ZFSResourceSetProperties
from middlewared.service_exception import ValidationError

from .create_rules import (
    apply_acl_defaults,
    reject_bad_acl_combination,
    reject_bad_user_property_names,
    reject_dedup_on_special_vdev,
    reject_tier_managed_ssb,
    reject_unentitled_dedup,
    size_bytes,
)
from .utils import reject_snapshot_path

if typing.TYPE_CHECKING:
    from middlewared.api.current import EntitlementEntry, ZFSResourceSetArgsData
    from middlewared.service import ServiceContext

__all__ = (
    "SETTABLE_PROPERTIES",
    "SetContext",
    "check_acl_combination",
    "check_dedup_entitlement",
    "check_dedup_tiering",
    "check_has_work",
    "check_inherit_names",
    "check_path_shape",
    "check_resource_exists",
    "check_set_inherit_conflict",
    "check_tier_managed_ssb",
    "check_user_property_names",
    "check_volsize_not_shrunk",
    "resolve_set_request",
)

SCHEMA = "zfs.resource.set"

_ACL_COMPANIONS = ("aclmode", "aclinherit")

SETTABLE_PROPERTIES: frozenset[str] = frozenset(ZFSResourceSetProperties.model_json_schema()["properties"])
"""The native property names an API caller may set, and therefore inherit.
Derived from the published schema so the `Private` and creation-only
fields drop out without a second list to maintain."""


@dataclasses.dataclass(slots=True, kw_only=True)
class SetContext:
    properties: ZFSResourceSetProperties
    """Effective zfs properties after the acl companions are filled in. A
    field left as None is not sent to ZFS."""
    inherit: set[str]
    """Effective names to inherit after the acltype fan-out."""
    current: dict[str, typing.Any] | None = None
    """The resource as it is now, with the properties the active rules
    read. Populated by the service; None when the resource does not
    exist."""
    tier_enabled: bool = False
    dedup_entitlement: EntitlementEntry | None = None
    """The DEDUP entitlement decision for this system. Populated by the
    service only when the request enables deduplication."""


def resolve_set_request(data: ZFSResourceSetArgsData) -> tuple[ZFSResourceSetProperties, set[str]]:
    """Apply the acltype coupling to both halves of the request.

    Setting acltype fills the companions the caller left alone (the
    creation defaults); inheriting acltype also inherits the companions
    the caller did not set. Nothing here raises.
    """
    properties = data.properties.model_copy()
    inherit = set(data.inherit)
    apply_acl_defaults(properties, leave=inherit)
    if "acltype" in inherit:
        inherit.update(name for name in _ACL_COMPANIONS if getattr(data.properties, name) is None)
    return properties, inherit


def check_path_shape(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    reject_snapshot_path(SCHEMA, data.path)


def check_has_work(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    if not (data.properties.model_dump(exclude_none=True) or data.user_properties or data.inherit):
        raise ValidationError(
            SCHEMA,
            "Nothing to update. Supply at least one of 'properties', 'user_properties' or 'inherit'.",
            errno.EINVAL,
        )


def check_set_inherit_conflict(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    setting = set(data.properties.model_dump(exclude_none=True)) | set(data.user_properties)
    for name in data.inherit:
        if name in setting:
            raise ValidationError(
                f"{SCHEMA}.inherit",
                f"{name!r} cannot be both set and inherited in the same request.",
                errno.EINVAL,
            )


def check_inherit_names(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    """A name to inherit is a user property or one of the settable native
    properties. Anything else would let a caller reset a property the
    public surface does not let it set."""
    for name in data.inherit:
        if ":" in name or name in SETTABLE_PROPERTIES:
            continue
        raise ValidationError(
            f"{SCHEMA}.inherit",
            f"{name!r} is not a property that may be inherited here. Native properties must be one of the "
            "settable properties and user property names must contain a colon.",
            errno.EINVAL,
        )


def check_user_property_names(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    reject_bad_user_property_names(SCHEMA, data.user_properties)


def check_resource_exists(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    """The resource must exist.

    The service calls this after the resource has been read.
    """
    if ctx.current is None:
        raise ValidationError(SCHEMA, f"{data.path!r} does not exist.", errno.ENOENT)


def check_volsize_not_shrunk(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    """A volume may only grow.

    The library drops a volsize equal to the current one before it
    reaches ZFS, so only a smaller value is refused. A value that is not
    a byte count is left for the library to judge.

    The service calls this only for volumes that request volsize and
    after the resource has been read.
    """
    assert ctx.current is not None
    try:
        requested = int(str(ctx.properties.volsize))
    except ValueError:
        return
    if requested < ctx.current["properties"]["volsize"]["value"]:
        raise ValidationError(
            f"{SCHEMA}.properties",
            f"'volsize' may not be reduced below the current size of {data.path!r}.",
            errno.EINVAL,
        )


def _effective_value(name: str, ctx: SetContext) -> str | None:
    assert ctx.current is not None
    value = getattr(ctx.properties, name)
    if value is None:
        value = ctx.current["properties"][name]["raw"]
    return str(value).lower() if value is not None else None


def check_acl_combination(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    """The service calls this only for filesystems that request acltype or aclmode and after the resource has
    been read."""
    reject_bad_acl_combination(SCHEMA, _effective_value("acltype", ctx), _effective_value("aclmode", ctx))


def check_tier_managed_ssb(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    """The tier manager owns special_small_blocks while tiering is enabled,
    so it may be neither set nor inherited.

    The service calls this only when tiering is enabled.
    """
    if "special_small_blocks" in data.inherit:
        raise ValidationError(
            f"{SCHEMA}.inherit",
            "ZFS tiering is enabled. Use `zfs.tier.dataset_set_tier` to manage 'special_small_blocks'.",
            errno.EINVAL,
        )
    reject_tier_managed_ssb(SCHEMA, data.properties.special_small_blocks)


def check_dedup_entitlement(data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    """The service calls this only for requests with a dedup value other than off and after the entitlement has
    been gathered."""
    assert ctx.dedup_entitlement is not None
    reject_unentitled_dedup(SCHEMA, ctx.dedup_entitlement)


def check_dedup_tiering(context: ServiceContext, data: ZFSResourceSetArgsData, ctx: SetContext) -> None:
    """The service calls this only for filesystems that request a dedup value other than off while tiering is
    enabled and after the resource has been read."""
    assert ctx.current is not None
    ssb = ctx.properties.special_small_blocks
    if ssb is None:
        ssb = ctx.current["properties"]["special_small_blocks"]["value"] or 0
    else:
        ssb = size_bytes(ssb) or 0
    reject_dedup_on_special_vdev(context, SCHEMA, data.path.split("/")[0], ssb)
