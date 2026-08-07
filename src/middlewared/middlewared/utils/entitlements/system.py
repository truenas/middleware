"""Evaluate entitlements for the system this process is running on.

The only module in this package that touches the system: it reads the license
and asks ``middlewared.utils.hardware`` what this machine is. Nothing else here
imports it, so the rest of the package stays pure and the engine can still be
evaluated against synthesized facts.

This is the single entry point for a live entitlement question. Callers name a
feature and nothing else; anything that builds ``EntitlementFacts`` by hand is
either a test, or a caller asking a question the policy does not answer -- alert
applicability being the one such caller, which is why ``get_facts`` is public.
"""

from __future__ import annotations

from middlewared.utils.hardware import get_hardware_class
from middlewared.utils.license import get_license

from .engine import Entitlement
from .facts import EntitlementFacts
from .policy import check_entitlement

__all__ = ("get_entitlement", "get_facts")


def get_facts() -> EntitlementFacts:
    """Read what this system is, right now.

    Deliberately not cached.
    ``get_hardware_class()`` is cheap after the
    first call in a process: ``get_hardware_info()`` is ``@cache``d,
    so only that first call pays for detection. That first call is not
    trivial -- besides forking dmidecode it may also fork ``ipmi-raw`` and
    issue SES ioctls to the enclosures, depending on the platform.
    """
    return EntitlementFacts(hardware_class=get_hardware_class(), license=get_license())


def get_entitlement(feature: str) -> Entitlement:
    """Return the entitlement for `feature` on this system."""
    return check_entitlement(feature, get_facts())
