"""Today-behavior legacy rules; grows during migration and is deleted once every feature flips to its matrix Vector."""

from __future__ import annotations

from truenas_pylicensed.features import LicenseFeature

from .engine import Entitlement, Reason, _format_message, has_key, resolve_column
from .facts import EntitlementFacts


def nvmet_spdk(facts: EntitlementFacts) -> Entitlement:
    # Today's is_enterprise semantics over facts, with the model-None guard:
    # entitled iff HA-capable, or a license is present for a non-freenas certified model.
    column = resolve_column(LicenseFeature.NVMEOF_SPDK, facts)
    model = facts.license.model if facts.license is not None else None
    entitled = facts.is_ha_capable or (
        facts.license is not None and model is not None and not model.lower().startswith("freenas")
    )
    if entitled:
        return Entitlement(entitled=True, reason=Reason.ENTITLED, column=column, message="")
    return Entitlement(
        entitled=False,
        reason=Reason.NO_LICENSE,
        column=column,
        message=_format_message(Reason.NO_LICENSE, LicenseFeature.NVMEOF_SPDK),
    )


def sed(facts: EntitlementFacts) -> Entitlement:
    # Membership-only key check over info_private facts (no expiry gating; legacy fallback restored).
    column = resolve_column(LicenseFeature.SED, facts)
    if has_key(LicenseFeature.SED, facts):
        return Entitlement(entitled=True, reason=Reason.ENTITLED, column=column, message="")
    reason = Reason.KEY_MISSING if facts.license is not None else Reason.NO_LICENSE
    return Entitlement(
        entitled=False,
        reason=reason,
        column=column,
        message=_format_message(reason, LicenseFeature.SED),
    )
