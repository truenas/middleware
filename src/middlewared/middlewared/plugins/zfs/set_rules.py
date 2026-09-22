"""Validation rules for zfs.resource.set.

Request rules judge the request alone and run before anything is read. Post-read rules are listed once in
`SET_RULES` and judge a `SetContext`, whose `effective()` resolves each property to the value it will have once the
request is applied. Shared checks come from rules_common as `reject_*` functions taking plain values.
"""

from __future__ import annotations

import dataclasses
import errno
import typing

from middlewared.api.current import ZFSResourceSetProperties
from middlewared.service_exception import CallError, ValidationError, ValidationErrors

from .rules_common import (
    reject_bad_acl_combination,
    reject_bad_user_property_names,
    reject_bad_user_property_values,
    reject_dedup_on_special_vdev,
    reject_tier_managed_ssb,
    reject_unentitled_dedup,
)

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping
    import logging

    from middlewared.api.current import EntitlementEntry, ZFSResourceSetArgsData
    from middlewared.service import ServiceContext

__all__ = (
    "INDEX_PROPERTIES",
    "INHERITABLE_PROPERTIES",
    "MODEL_NATIVES",
    "NON_INHERITABLE_PROPERTIES",
    "POOL_ROOT_INHERIT_VALUES",
    "SETTABLE_PROPERTIES",
    "SET_READ_PROPERTIES",
    "SET_RULES",
    "PropertyView",
    "SetContext",
    "SetRule",
    "check_acl_combination",
    "check_dedup_entitlement",
    "check_dedup_tiering",
    "check_has_work",
    "check_inherit_names",
    "check_set_inherit_conflict",
    "check_tier_managed_ssb",
    "check_user_properties",
    "check_volsize_not_shrunk",
    "touched_natives",
    "validate_request",
    "validate_set",
)

SCHEMA = "zfs.resource.set"

SETTABLE_PROPERTIES: frozenset[str] = frozenset(ZFSResourceSetProperties.model_json_schema()["properties"])
"""The native property names an API caller may set. Derived from the published schema so the `Private` and
creation-only fields drop out without a second list to maintain."""

NON_INHERITABLE_PROPERTIES = frozenset({"quota", "refquota", "reservation", "refreservation", "volsize"})
INHERITABLE_PROPERTIES = SETTABLE_PROPERTIES - NON_INHERITABLE_PROPERTIES
MODEL_NATIVES = frozenset(name for name, field in ZFSResourceSetProperties.model_fields.items() if not field.exclude)
"""Every native the set model carries, the `Private` ones included."""
INDEX_PROPERTIES = frozenset(
    {
        "aclinherit",
        "aclmode",
        "acltype",
        "atime",
        "checksum",
        "compression",
        "dedup",
        "exec",
        "readonly",
        "snapdev",
        "snapdir",
        "sync",
        "xattr",
    }
)
SET_READ_PROPERTIES = SETTABLE_PROPERTIES | {"available", "volblocksize", "usedbyrefreservation"}
POOL_ROOT_INHERIT_VALUES: Mapping[str, typing.Any] = {  # registered ZFS defaults; pylibzfs has no accessor for them
    "acltype": "nfsv4",
    "aclmode": "discard",
    "aclinherit": "restricted",
    "dedup": "off",
    "special_small_blocks": 0,
}


class PropertyView(dict[str, typing.Any]):
    """Property values read for one resource. A name that was not read, or was read without a value, raises
    `CallError` when indexed; `.get()` is a plain lookup."""

    __slots__ = ("path",)

    def __init__(self, path: str, values: Mapping[str, typing.Any]) -> None:
        super().__init__(values)
        self.path = path

    def __missing__(self, key: str) -> typing.NoReturn:
        raise CallError(f"{key!r} was not read for {self.path!r}")

    def __getitem__(self, key: str) -> typing.Any:
        value = super().__getitem__(key)
        if value is None:
            self.__missing__(key)
        return value


def touched_natives(properties: ZFSResourceSetProperties, inherit: Collection[str]) -> frozenset[str]:
    """The native properties a request sets or inherits."""
    return frozenset(name for name in MODEL_NATIVES if getattr(properties, name) is not None) | {
        name for name in inherit if ":" not in name
    }


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class SetContext:
    path: str
    type: typing.Literal["FILESYSTEM", "VOLUME"]
    properties: ZFSResourceSetProperties
    """What will be sent to ZFS. A field left as None is not touched."""
    user_properties: Mapping[str, str]
    inherit: frozenset[str]
    """Names to inherit, user property names included."""
    current: PropertyView
    """Values on the resource now. A name absent here is not valid for the resource's type."""
    source: PropertyView
    """The source type of each value in `current`."""
    parent: PropertyView | None
    """Values on the parent; None when no native is inherited or the resource is a pool root."""
    pool_root: bool
    tier_enabled: bool | None
    """None when the request touches nothing the tier manager owns, so the tier config was not read."""
    dedup_entitlement: EntitlementEntry | None
    """None when the request does not touch dedup."""
    derived: frozenset[str] = frozenset()
    """Names middleware added to the request on the caller's behalf."""
    snapshot_devices: frozenset[str] = frozenset()

    def set_names(self) -> frozenset[str]:
        return frozenset(name for name in MODEL_NATIVES if getattr(self.properties, name) is not None)

    def inherited_natives(self) -> frozenset[str]:
        return frozenset(name for name in self.inherit if ":" not in name)

    def touched(self) -> frozenset[str]:
        return touched_natives(self.properties, self.inherit)

    def changed(self, name: str) -> bool:
        return bool(self.effective(name) != self.current.get(name))

    def attribute(self, name: str) -> str:
        if name in self.set_names():
            return f"{SCHEMA}.properties.{name}"
        return f"{SCHEMA}.inherit.{name}"

    def effective(self, name: str) -> typing.Any:
        """The value `name` will have once the request is applied."""
        if name in self.set_names():
            value = getattr(self.properties, name)
            return str(value).lower() if name in INDEX_PROPERTIES else value
        if name in self.inherited_natives():
            if self.parent is not None and name in self.parent:
                return self.parent[name]
            if self.pool_root and name in POOL_ROOT_INHERIT_VALUES:
                return POOL_ROOT_INHERIT_VALUES[name]
            raise CallError(f"{name!r} has no source to inherit from on {self.path!r}")
        return self.current[name]


def check_has_work(data: ZFSResourceSetArgsData, verrors: ValidationErrors) -> None:
    if not (data.properties.model_dump(exclude_none=True) or data.user_properties or data.inherit):
        verrors.add(
            SCHEMA,
            "Nothing to update. Supply at least one of 'properties', 'user_properties' or 'inherit'.",
            errno.EINVAL,
        )


def check_set_inherit_conflict(data: ZFSResourceSetArgsData, verrors: ValidationErrors) -> None:
    setting = set(data.properties.model_dump(exclude_none=True)) | set(data.user_properties)
    for name in data.inherit:
        if name in setting:
            verrors.add(
                f"{SCHEMA}.inherit.{name}",
                f"{name!r} cannot be both set and inherited in the same request.",
                errno.EINVAL,
            )


def check_inherit_names(data: ZFSResourceSetArgsData, verrors: ValidationErrors) -> None:
    user_names = []
    for name in data.inherit:
        if ":" in name:
            user_names.append(name)
        elif name in NON_INHERITABLE_PROPERTIES:
            verrors.add(f"{SCHEMA}.inherit.{name}", f"{name!r} has no inherited value.", errno.EINVAL)
        elif name not in INHERITABLE_PROPERTIES:
            verrors.add(f"{SCHEMA}.inherit.{name}", f"{name!r} is not a settable property.", errno.EINVAL)
    reject_bad_user_property_names(verrors, f"{SCHEMA}.inherit", user_names)


def check_user_properties(data: ZFSResourceSetArgsData, verrors: ValidationErrors) -> None:
    reject_bad_user_property_names(verrors, f"{SCHEMA}.user_properties", data.user_properties)
    reject_bad_user_property_values(verrors, f"{SCHEMA}.user_properties", data.user_properties)


def validate_request(data: ZFSResourceSetArgsData, verrors: ValidationErrors) -> None:
    """Judge what the request alone decides. Reads nothing."""
    check_has_work(data, verrors)
    check_set_inherit_conflict(data, verrors)
    check_inherit_names(data, verrors)
    check_user_properties(data, verrors)


def check_volsize_not_shrunk(context: ServiceContext, state: SetContext, verrors: ValidationErrors) -> None:
    if state.type != "VOLUME" or "volsize" not in state.set_names():
        return
    if state.effective("volsize") < state.current["volsize"]:
        verrors.add(
            state.attribute("volsize"),
            f"'volsize' may not be reduced below the current size of {state.path!r}.",
            errno.EINVAL,
        )


def check_acl_combination(context: ServiceContext, state: SetContext, verrors: ValidationErrors) -> None:
    if state.type != "FILESYSTEM":
        return
    attribute = state.attribute("aclmode" if "aclmode" in state.touched() else "acltype")
    reject_bad_acl_combination(verrors, attribute, state.effective("acltype"), state.effective("aclmode"))


def check_tier_managed_ssb(context: ServiceContext, state: SetContext, verrors: ValidationErrors) -> None:
    if not state.tier_enabled:
        return
    if "special_small_blocks" in state.set_names():
        if state.effective("special_small_blocks") == state.current["special_small_blocks"]:
            return
    elif state.source["special_small_blocks"] in ("INHERITED", "DEFAULT", "NONE"):
        return
    reject_tier_managed_ssb(verrors, state.attribute("special_small_blocks"))


def check_dedup_entitlement(context: ServiceContext, state: SetContext, verrors: ValidationErrors) -> None:
    if state.effective("dedup") == "off" or not state.changed("dedup"):
        return
    if state.dedup_entitlement is None:
        raise CallError(f"The DEDUP entitlement was not read for {state.path!r}")
    reject_unentitled_dedup(verrors, state.attribute("dedup"), state.dedup_entitlement)


def check_dedup_tiering(context: ServiceContext, state: SetContext, verrors: ValidationErrors) -> None:
    if state.type != "FILESYSTEM" or not state.tier_enabled:
        return
    ssb = state.effective("special_small_blocks")
    if state.effective("dedup") == "off" or ssb <= 0:
        return
    if not (state.changed("dedup") or state.changed("special_small_blocks")):
        return
    attribute = state.attribute("dedup" if "dedup" in state.touched() else "special_small_blocks")
    reject_dedup_on_special_vdev(verrors, attribute, context, state.path.split("/")[0], ssb)


class SetRule(typing.NamedTuple):
    check: Callable[[ServiceContext, SetContext, ValidationErrors], None]
    triggers: frozenset[str]


SET_RULES: tuple[SetRule, ...] = (
    SetRule(check_volsize_not_shrunk, frozenset({"volsize"})),
    SetRule(check_acl_combination, frozenset({"acltype", "aclmode"})),
    SetRule(check_tier_managed_ssb, frozenset({"special_small_blocks"})),
    SetRule(check_dedup_entitlement, frozenset({"dedup"})),
    SetRule(check_dedup_tiering, frozenset({"dedup", "special_small_blocks"})),
)


def validate_set(
    context: ServiceContext, state: SetContext, verrors: ValidationErrors, logger: logging.Logger
) -> list[tuple[str, Exception]]:
    """Run every rule the request triggers, adding what they find to `verrors`. Never raises.

    A rule that fails with anything but a validation error is logged and returned as `(rule name, exception)` so
    the caller can refuse the request once every other rule has had its say.
    """
    failures: list[tuple[str, Exception]] = []
    touched = state.touched()
    for rule in SET_RULES:
        if not rule.triggers & touched:
            continue
        name = rule.check.__name__
        try:
            rule.check(context, state, verrors)
        except ValidationError as e:
            verrors.add_validation_error(e)
        except ValidationErrors as e:
            for error in e.errors:
                verrors.add_validation_error(error)
        except Exception as e:
            logger.error("%s: rule %s failed", state.path, name, exc_info=True)
            failures.append((name, e))
    return failures
