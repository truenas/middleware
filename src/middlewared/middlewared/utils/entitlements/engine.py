from __future__ import annotations

import typing
from dataclasses import dataclass
from enum import StrEnum

from truenas_pylicensed.features import LicenseFeature

from .facts import EntitlementFacts, HardwareClass

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from truenas_pylicensed import LicenseType


COLUMNS: tuple[str, ...] = ("CE", "HW", "HW+L", "HW+K", "CE+L", "CE+K")


class Reason(StrEnum):
    ENTITLED = "ENTITLED"
    NO_LICENSE = "NO_LICENSE"
    KEY_MISSING = "KEY_MISSING"
    WRONG_HARDWARE = "WRONG_HARDWARE"
    TIER_INSUFFICIENT = "TIER_INSUFFICIENT"
    WRONG_LICENSE_TYPE = "WRONG_LICENSE_TYPE"


class DerivedEntitlement(StrEnum):
    """Entitlements computed from license type/tier rather than a license feature flag."""

    HA = "HA"
    PROACTIVE_SUPPORT = "PROACTIVE_SUPPORT"


_MESSAGES: Mapping[Reason, str] = {
    Reason.ENTITLED: "",
    Reason.NO_LICENSE: "This system is not licensed to use the {feature} feature.",
    Reason.KEY_MISSING: "This system's license does not include the {feature} feature.",
    Reason.WRONG_HARDWARE: "The {feature} feature is not available on this system's hardware.",
    Reason.TIER_INSUFFICIENT: "This system's support tier does not include the {feature} feature.",
    Reason.WRONG_LICENSE_TYPE: "This system's license type does not include the {feature} feature.",
}

# Human-facing names substituted into the generic message templates; the raw
# feature key is used when a name is not listed here.
FEATURE_DISPLAY_NAMES: Mapping[str, str] = {
    LicenseFeature.APPS: "applications",
    LicenseFeature.CONTAINERS: "containers",
    LicenseFeature.DEDUP: "ZFS deduplication",
    LicenseFeature.DIRECTORY_SERVICES: "directory services authentication",
    LicenseFeature.FIBRECHANNEL: "Fibre Channel",
    LicenseFeature.KMIP: "KMIP key management",
    LicenseFeature.NETWORK_FEC: "FEC mode configuration",
    LicenseFeature.NFS_SNAPSHOT: "NFS snapshot exposure",
    LicenseFeature.NVMEOF_SPDK: "NVMe-oF SPDK backend",
    LicenseFeature.RDMA: "RDMA",
    LicenseFeature.SED: "SED",
    LicenseFeature.SMB_FASTPATH: "SMB ZFS fastpath",
    LicenseFeature.SMB_VEEAM: "Veeam repository shares",
    LicenseFeature.STIG: "STIG and FIPS",
    LicenseFeature.SUPPORT: "support",
    LicenseFeature.TRUESEARCH: "TrueSearch",
    LicenseFeature.VMS: "virtual machines",
    LicenseFeature.WEBSHARE: "Webshare",
    LicenseFeature.ZFSTIER: "ZFS tiering",
    DerivedEntitlement.HA: "high availability",
    DerivedEntitlement.PROACTIVE_SUPPORT: "proactive support",
}

# Per-feature, per-reason message overrides consulted before the generic
# templates. Lets a feature keep bespoke wording that would otherwise be lost
# when its rule flips from a LegacyRule to a matrix Vector.
FEATURE_MESSAGES: Mapping[str, Mapping[Reason, str]] = {
    LicenseFeature.DIRECTORY_SERVICES: {
        Reason.NO_LICENSE: "Directory services authentication for UI and API access requires an Enterprise license.",
        Reason.KEY_MISSING: "Directory services authentication for UI and API access requires an Enterprise license.",
        Reason.WRONG_HARDWARE: (
            "Directory services authentication for UI and API access requires an Enterprise license."
        ),
    },
    LicenseFeature.NETWORK_FEC: {
        Reason.NO_LICENSE: "Configuring FEC mode is an enterprise feature.",
        Reason.KEY_MISSING: "Configuring FEC mode is an enterprise feature.",
        Reason.WRONG_HARDWARE: "Configuring FEC mode is an enterprise feature.",
    },
    LicenseFeature.NFS_SNAPSHOT: {
        Reason.NO_LICENSE: "This is an enterprise feature and may not be enabled without a valid license.",
        Reason.KEY_MISSING: "This is an enterprise feature and may not be enabled without a valid license.",
        Reason.WRONG_HARDWARE: "This is an enterprise feature and may not be enabled without a valid license.",
    },
    LicenseFeature.NVMEOF_SPDK: {
        Reason.NO_LICENSE: "SPDK is limited to enterprise licensed systems only.",
        Reason.KEY_MISSING: "SPDK is limited to enterprise licensed systems only.",
        Reason.WRONG_HARDWARE: "SPDK is limited to enterprise licensed systems only.",
    },
    LicenseFeature.SMB_VEEAM: {
        Reason.NO_LICENSE: "Veeam repository shares require a TrueNAS enterprise license.",
        Reason.KEY_MISSING: "Veeam repository shares require a TrueNAS enterprise license.",
        Reason.WRONG_HARDWARE: "Veeam repository shares require a TrueNAS enterprise license.",
    },
}


def _format_message(reason: Reason, feature: str) -> str:
    overrides = FEATURE_MESSAGES.get(feature)
    if overrides is not None and reason in overrides:
        return overrides[reason]
    display = FEATURE_DISPLAY_NAMES.get(feature, feature)
    return _MESSAGES[reason].format(feature=display)


@dataclass(frozen=True, kw_only=True, slots=True)
class Entitlement:
    entitled: bool
    """Whether the system is entitled to the feature."""
    reason: Reason
    """Machine-readable classification of the outcome."""
    column: str
    """Feature-matrix column the facts resolved to (one of COLUMNS)."""
    message: str
    """Human-facing explanation, empty when entitled."""


class Vector(typing.NamedTuple):
    ce: int
    hw: int
    hw_l: int
    hw_k: int
    ce_l: int
    ce_k: int


@dataclass(frozen=True, kw_only=True, slots=True)
class LegacyRule:
    func: Callable[[EntitlementFacts], Entitlement]
    """Callable reproducing a today-behavior gate over the given facts."""


@dataclass(frozen=True, kw_only=True, slots=True)
class TierRule:
    feature: str
    """License feature whose per-feature ``type`` qualifier is inspected (e.g. "SUPPORT")."""
    allowed_tiers: frozenset[str]
    """Tier values (upper-cased) that grant the checked feature."""


@dataclass(frozen=True, kw_only=True, slots=True)
class LicenseTypeRule:
    allowed_types: frozenset[LicenseType]
    """License types that grant the checked feature."""


Rule = typing.Union[Vector, LegacyRule, TierRule, LicenseTypeRule]


def has_key(feature: str, facts: EntitlementFacts) -> bool:
    """Membership-only key check: True iff a license is present and carries the feature."""
    return facts.license is not None and facts.license.has_feature(feature)


def _hw_side(facts: EntitlementFacts) -> bool:
    return facts.hardware_class is HardwareClass.TRUENAS_HW


def resolve_column(feature: str, facts: EntitlementFacts) -> str:
    hw_side = _hw_side(facts)
    if facts.license is None:
        return "HW" if hw_side else "CE"
    if has_key(feature, facts):
        return "HW+K" if hw_side else "CE+K"
    return "HW+L" if hw_side else "CE+L"


def _check_vector(feature: str, vector: Vector, facts: EntitlementFacts) -> Entitlement:
    hw_side = _hw_side(facts)
    column = resolve_column(feature, facts)
    if vector[COLUMNS.index(column)]:
        return Entitlement(entitled=True, reason=Reason.ENTITLED, column=column, message="")

    # A key on this hardware side is what would grant the feature. If that cell
    # is set, the feature is achievable here (license missing vs key missing);
    # otherwise this hardware can never have it.
    key_cell = vector.hw_k if hw_side else vector.ce_k
    reason: Reason
    if key_cell:
        reason = Reason.KEY_MISSING if facts.license is not None else Reason.NO_LICENSE
    else:
        reason = Reason.WRONG_HARDWARE

    return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, feature))


def _check_tier(feature: str, rule: TierRule, facts: EntitlementFacts) -> Entitlement:
    column = resolve_column(feature, facts)
    if facts.license is None:
        reason: Reason = Reason.NO_LICENSE
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, feature))

    info = facts.license.feature(rule.feature)
    if info is None:
        reason = Reason.KEY_MISSING
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, feature))

    if info.type is None or info.type.upper() not in rule.allowed_tiers:
        reason = Reason.TIER_INSUFFICIENT
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, feature))

    return Entitlement(entitled=True, reason=Reason.ENTITLED, column=column, message="")


def _check_license_type(feature: str, rule: LicenseTypeRule, facts: EntitlementFacts) -> Entitlement:
    column = resolve_column(feature, facts)
    if facts.license is None:
        reason: Reason = Reason.NO_LICENSE
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, feature))

    if facts.license.type not in rule.allowed_types:
        reason = Reason.WRONG_LICENSE_TYPE
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, feature))

    return Entitlement(entitled=True, reason=Reason.ENTITLED, column=column, message="")
