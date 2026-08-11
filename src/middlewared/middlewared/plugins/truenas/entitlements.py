from typing import Annotated

from pydantic import BeforeValidator

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.service import Service
from middlewared.utils.entitlements import DerivedEntitlement, EntitlementKey, LicenseFeature, get_entitlement


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
        private = True

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
