from __future__ import annotations

import typing
from dataclasses import dataclass
from enum import StrEnum

from truenas_pylicensed.features import LicenseFeature

from .facts import EntitlementFacts

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
    NOT_GATED = "NOT_GATED"


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
    Reason.NOT_GATED: "",
}

# Human-facing names substituted into the generic message templates; the raw
# feature key is used when a name is not listed here.
FEATURE_DISPLAY_NAMES: Mapping[str, str] = {
    LicenseFeature.APPS: "applications",
    LicenseFeature.CATALOG_ENTERPRISE_TRAIN: "enterprise application train",
    LicenseFeature.CONTAINERS: "containers",
    LicenseFeature.DEDUP: "ZFS deduplication",
    LicenseFeature.DIRECTORY_SERVICES: "directory services authentication",
    LicenseFeature.FIBRECHANNEL: "Fibre Channel",
    LicenseFeature.KMIP: "KMIP key management",
    LicenseFeature.MISSION_CRITICAL: "Mission Critical update profile",
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
    return _MESSAGES.get(reason, "").format(feature=display)


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
    """One row of the product feature matrix: six cells, where ``1`` grants and ``0`` denies.

    Field order is ``COLUMNS`` order. That is the whole reason the engine can index a row by
    the column the facts resolved to (``vector[COLUMNS.index(column)]``).

    Which half of the row a system reads is decided by ``facts.hardware_class.is_appliance``:
    iX appliance hardware takes the ``hw*`` cells and everything else takes the ``ce*`` cells.
    Minis are iX hardware but fold to the CE side. Within a half the license axis has three
    states -- no license at all, a license that does not carry this feature's key, and a
    license that does.

    So a license without the key is its own population rather than a superset of the
    unlicensed one, and a row can grant ``ce`` while leaving ``ce_l`` clear: the feature is
    available on an unlicensed community system and is revoked the moment a license lands
    that omits the key. That falls out of column resolution and is never special-cased.
    """

    ce: int
    """CE side -- non-appliance hardware and Minis -- with no license present."""
    hw: int
    """Appliance hardware with no license present."""
    hw_l: int
    """Appliance hardware licensed, where the license does not carry this feature's key."""
    hw_k: int
    """Appliance hardware licensed, where the license carries this feature's key."""
    ce_l: int
    """CE side licensed, where the license does not carry this feature's key."""
    ce_k: int
    """CE side licensed, where the license carries this feature's key."""


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
    vector: Vector
    """Matrix cells for this entitlement, authoritative for the resolved column.

    Only ``hw_k`` and ``ce_k`` may be set, and anything else is rejected outright. A tier
    is read off ``FeatureInfo.type``, which exists only where the feature's key does, so a
    cell set anywhere else would claim a tier could be evaluated with no key to read it
    from.

    ``LicenseInfo.contract_type`` is deliberately not consulted as a second source of
    a tier: on a daemon license it is derived from this same feature, so it is absent
    in exactly the columns where the key is.
    """

    def __post_init__(self) -> None:
        vector = self.vector
        if vector.ce or vector.hw or vector.hw_l or vector.ce_l:
            raise ValueError(
                f"TierRule({self.feature}): a tier is read off a feature key, so it cannot be "
                f"evaluated without one. Only hw_k/ce_k may be set; got {vector}."
            )


@dataclass(frozen=True, kw_only=True, slots=True)
class LicenseTypeRule:
    allowed_types: frozenset[LicenseType]
    """License types that grant the checked feature."""


Rule = typing.Union[Vector, LegacyRule, TierRule, LicenseTypeRule]

# Anything the policy can be keyed by. A license carries its own feature keys, and
# some entitlements exist only here because they fall out of the license type or
# tier instead of a key, so both vocabularies are equally valid to ask about.
EntitlementKey = LicenseFeature | DerivedEntitlement


def has_key(feature: str, facts: EntitlementFacts) -> bool:
    """Membership-only key check: True iff a license is present and carries the feature."""
    return facts.license is not None and facts.license.has_feature(feature)


def resolve_column(key_feature: str, facts: EntitlementFacts) -> str:
    """Return the matrix column `facts` resolves to, keyed off `key_feature`.

    `key_feature` is the license feature whose *key presence* decides the K axis, which
    is not always the entitlement being checked: a rule whose policy key is not itself
    a license feature key has to name the feature that carries its qualifier instead,
    or the K columns are unreachable.
    """
    hw_side = facts.hardware_class.is_appliance
    if facts.license is None:
        return "HW" if hw_side else "CE"
    if has_key(key_feature, facts):
        return "HW+K" if hw_side else "CE+K"
    return "HW+L" if hw_side else "CE+L"


def _vector_deny_reason(vector: Vector, facts: EntitlementFacts) -> Reason:
    """Classify a vector's denial.

    A key on this hardware side is what would grant the feature. If that cell is set,
    the feature is achievable here (license missing vs key missing); otherwise this
    hardware can never have it. Every rule kind that resolves by column shares this, so
    their denials cannot drift apart.
    """
    key_cell = vector.hw_k if facts.hardware_class.is_appliance else vector.ce_k
    if not key_cell:
        return Reason.WRONG_HARDWARE
    return Reason.KEY_MISSING if facts.license is not None else Reason.NO_LICENSE


def _check_vector(feature: str, vector: Vector, facts: EntitlementFacts) -> Entitlement:
    column = resolve_column(feature, facts)
    if vector[COLUMNS.index(column)]:
        return Entitlement(entitled=True, reason=Reason.ENTITLED, column=column, message="")

    reason = _vector_deny_reason(vector, facts)
    return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, feature))


def _check_tier(policy_key: str, rule: TierRule, facts: EntitlementFacts) -> Entitlement:
    """Resolve `rule` against its matrix row, then qualify the grant by the feature's tier.

    The vector decides the column and is authoritative -- a tier cannot rescue a cell the
    matrix does not grant, which is why the cell is read first. Because the vector is
    key-only, a granting cell means the column is ``HW+K``/``CE+K``, so the tier is only
    ever asked where the key that carries it exists.

    The column resolves against ``rule.feature`` -- the key that carries the tier -- while
    messages are formatted from `policy_key`. The two differ: proactive support is
    qualified by the SUPPORT key, and "support" is not its wording.
    """
    column = resolve_column(rule.feature, facts)
    if not rule.vector[COLUMNS.index(column)]:
        reason = _vector_deny_reason(rule.vector, facts)
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, policy_key))

    info = facts.license.feature(rule.feature) if facts.license is not None else None
    if info is None:
        # Unreachable while the vector stays key-only, since a granting cell is a K column
        # and that is exactly where the license carries the feature. Kept as the narrowing
        # for facts.license, and so that relaxing the constraint degrades to a denial rather
        # than to an AttributeError.
        reason = Reason.KEY_MISSING
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, policy_key))

    if info.type is None or info.type.upper() not in rule.allowed_tiers:
        reason = Reason.TIER_INSUFFICIENT
        return Entitlement(entitled=False, reason=reason, column=column, message=_format_message(reason, policy_key))

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
