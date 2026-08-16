from typing import Annotated

from pydantic import BeforeValidator

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    EntitlementEntry,
    EntitlementsInfo,
    TrueNASEntitlementsFeatureArgs,
    TrueNASEntitlementsFeatureResult,
    TrueNASEntitlementsInfoArgs,
    TrueNASEntitlementsInfoResult,
)
from middlewared.service import Service
from middlewared.utils.entitlements import (
    POLICY,
    DerivedEntitlement,
    EntitlementKey,
    LicenseFeature,
    Reason,
    check_entitlement,
    get_entitlement,
    get_facts,
)


def coerce_entitlement_key(value: object) -> object:
    """Resolve a feature name to its enum member before the strict field check sees it.

    Over the wire a feature arrives as a plain string, which a strict enum-typed field would
    reject outright, and its own rejection message says nothing about which names are legal.
    Non-string values are left alone so the strict check still refuses them.
    """
    if isinstance(value, LicenseFeature | DerivedEntitlement) or not isinstance(value, str):
        return value

    for vocabulary in (LicenseFeature, DerivedEntitlement):
        try:
            return vocabulary(value)
        except ValueError:
            continue

    raise ValueError(f"{value!r} is neither a license feature nor a derived entitlement")


class TrueNASEntitlementsCheckArgs(BaseModel):
    feature: Annotated[EntitlementKey, BeforeValidator(coerce_entitlement_key)]


class TrueNASEntitlementsCheckEntitlement(BaseModel):
    """API representation of an entitlement decision."""

    entitled: bool
    reason: str
    column: str
    message: str


class TrueNASEntitlementsCheckResult(BaseModel):
    result: TrueNASEntitlementsCheckEntitlement


class TrueNASEntitlementsService(Service):
    class Config:
        namespace = "truenas.entitlements"
        cli_private = True

    @api_method(
        TrueNASEntitlementsCheckArgs,
        TrueNASEntitlementsCheckResult,
        private=True,
        check_annotations=True,
    )
    def check(self, feature: EntitlementKey) -> TrueNASEntitlementsCheckEntitlement:
        """Return the entitlement for `feature` computed from current system facts."""
        entitlement = get_entitlement(feature)
        # `middlewared.utils.entitlements.Entitlement` and the model above are two
        # representations of one concept, and they stay apart on purpose. The engine is a pure
        # package -- importing `middlewared.api.base` into it would break the
        # `entitlements_layers` import contract -- so `get_entitlement()` keeps returning the
        # dataclass, and callers that bypass this endpoint (`failover_/ha_hardware.py`) still
        # get it. This method is the only place the two meet; do not "unify" them.
        return TrueNASEntitlementsCheckEntitlement(
            entitled=entitlement.entitled,
            reason=entitlement.reason,
            column=entitlement.column,
            message=entitlement.message,
        )

    @api_method(
        TrueNASEntitlementsFeatureArgs,
        TrueNASEntitlementsFeatureResult,
        roles=["SYSTEM_PRODUCT_READ"],
        check_annotations=True,
    )
    def feature(self, feature: str) -> EntitlementEntry:
        """Return the entitlement decision for `feature`."""
        try:
            entitlement = get_entitlement(feature)
        except ValueError:
            # The engine raises for a key it has no rule for. Over the API that is not an error:
            # the issuer's vocabulary can run ahead of ours, and a feature nothing here gates is a
            # feature nothing here restricts. Internal callers keep the raise -- they name features
            # as enum members, so a missing rule for one of those is a bug worth failing on.
            return EntitlementEntry(entitled=True, reason=Reason.NOT_GATED, message="")

        # `column` is left out for the same reason `info` omits it: it is the matrix coordinate
        # the facts resolved to, and publishing it would make the matrix's shape a contract.
        return EntitlementEntry(
            entitled=entitlement.entitled,
            reason=entitlement.reason,
            message=entitlement.message,
        )

    @api_method(
        TrueNASEntitlementsInfoArgs,
        TrueNASEntitlementsInfoResult,
        roles=["SYSTEM_PRODUCT_READ"],
        check_annotations=True,
    )
    def info(self) -> EntitlementsInfo:
        """Return the entitlement decision for every license-gated feature."""
        # Read the facts once and evaluate the pure policy against them. `get_facts()` is
        # uncached and its license read is a round trip to the license daemon, so asking
        # `get_entitlement()` per feature would pay for that round trip once per key.
        facts = get_facts()
        features: dict[str, EntitlementEntry] = {}
        # `POLICY` rather than the feature vocabulary: some license features deliberately
        # have no rule, and `check_entitlement` raises for a key it cannot resolve.
        for key in POLICY:
            entitlement = check_entitlement(key, facts)
            # `column` is left out on purpose. It is the matrix coordinate the facts
            # resolved to, and publishing it would make the matrix's shape a contract.
            features[str(key)] = EntitlementEntry(
                entitled=entitlement.entitled,
                reason=entitlement.reason,
                message=entitlement.message,
            )

        return EntitlementsInfo(features=features)
