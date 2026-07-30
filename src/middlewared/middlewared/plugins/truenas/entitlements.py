from __future__ import annotations

from middlewared.service import Service
from middlewared.utils.entitlements import Entitlement, get_entitlement


class TrueNASEntitlementsService(Service):
    class Config:
        namespace = "truenas.entitlements"
        private = True

    def check(self, feature: str) -> Entitlement:
        """Return the entitlement for `feature` computed from current system facts."""
        return get_entitlement(feature)
