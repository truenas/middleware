from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.service import Service
from middlewared.utils.entitlements import get_entitlement


class TrueNASEntitlementsCheckArgs(BaseModel):
    feature: str


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
    def check(self, feature: str) -> TrueNASEntitlementsCheckEntitlement:
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
