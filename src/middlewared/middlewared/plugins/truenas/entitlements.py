from __future__ import annotations

from middlewared.service import Service
from middlewared.utils.entitlements import (
    Entitlement,
    EntitlementFacts,
    HardwareClass,
    check_entitlement,
)

from .tn import get_chassis_hardware


class TrueNASEntitlementsService(Service):
    class Config:
        namespace = "truenas.entitlements"
        private = True

    def check(self, feature: str) -> Entitlement:
        """Return the entitlement for `feature` computed from current system facts."""
        # TODO: facts are re-gathered on every call, so every call is a license daemon
        # round-trip through info_private. The smb.conf render path calls this once per
        # etc.generate, where the is_enterprise read it replaced was a memoized class
        # attribute. Confirm a failure to reach the daemon cannot stop smb.conf from
        # rendering at all.
        return check_entitlement(feature, self._gather_facts())

    def _gather_facts(self) -> EntitlementFacts:
        return EntitlementFacts(
            hardware_class=HardwareClass.from_chassis(get_chassis_hardware()),
            license=self.call_sync2(self.s.truenas.license.info_private),
        )
