from __future__ import annotations

from middlewared.service import Service
from middlewared.utils.entitlements import (
    Entitlement,
    EntitlementFacts,
    HardwareClass,
    check as check_entitlement,
)

from .tn import get_chassis_hardware


class TrueNASEntitlementsService(Service):
    class Config:
        namespace = "truenas.entitlements"
        private = True

    def check(self, feature: str) -> Entitlement:
        """Return the entitlement for `feature` computed from current system facts."""
        return check_entitlement(feature, self._gather_facts())

    def _gather_facts(self) -> EntitlementFacts:
        return EntitlementFacts(
            hardware_class=HardwareClass.from_chassis(get_chassis_hardware()),
            is_ha_capable=self.middleware.call_sync("failover.hardware") != "MANUAL",
            license=self.call_sync2(self.s.truenas.license.info_private),
        )
