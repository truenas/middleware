from __future__ import annotations

from truenas_pylicensed.features import LicenseFeature

from .engine import Entitlement, Reason, _format_message, has_key, resolve_column
from .facts import EntitlementFacts


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
