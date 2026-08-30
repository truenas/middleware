from middlewared.api import api_method
from middlewared.api.current import (
    EntitlementEntry,
    EntitlementsInfo,
    TrueNASEntitlementsCheckArgs,
    TrueNASEntitlementsCheckResult,
    TrueNASEntitlementsInfoArgs,
    TrueNASEntitlementsInfoResult,
)
from middlewared.service import Service
from middlewared.utils.entitlements import (
    POLICY,
    Entitlement,
    Reason,
    check_entitlement,
    get_entitlement,
    get_facts,
)


def _entry(entitlement: Entitlement) -> EntitlementEntry:
    """Project an engine decision onto its API representation.

    The engine is a pure package, and importing `middlewared.api.base` into it would break the
    `entitlements_layers` import contract. So `get_entitlement()` keeps returning the dataclass,
    and callers that do not go through this service (`failover_/ha_hardware.py`) still get it.
    This function is the only place the two meet.

    `column` is not carried across. It is the matrix coordinate the facts resolved to, and
    publishing it would make the matrix's shape a contract.
    """
    return EntitlementEntry(
        entitled=entitlement.entitled,
        reason=entitlement.reason,
        message=entitlement.message,
    )


class TrueNASEntitlementsService(Service):
    class Config:
        namespace = "truenas.entitlements"
        cli_private = True

    @api_method(
        TrueNASEntitlementsCheckArgs,
        TrueNASEntitlementsCheckResult,
        roles=["SYSTEM_PRODUCT_READ"],
        check_annotations=True,
    )
    def check(self, feature: str) -> EntitlementEntry:
        """Return the entitlement for `feature` computed from current system facts.

        A caller may name a feature by its vocabulary member or by its plain name; both arrive
        here as the name, and `POLICY` is keyed by members whose hash is the plain string's.
        """
        try:
            entitlement = get_entitlement(feature)
        except ValueError:
            # `POLICY` is the register of what this product gates, so a key it does not carry
            # is a decision rather than an error: nothing on this system restricts the feature.
            # The engine still raises, because a lookup must not invent an answer.
            return EntitlementEntry(entitled=True, reason=Reason.NOT_GATED, message="")

        return _entry(entitlement)

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
            features[str(key)] = _entry(check_entitlement(key, facts))

        return EntitlementsInfo(features=features)
