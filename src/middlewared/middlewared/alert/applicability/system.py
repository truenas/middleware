"""Read the applicability facts of the system this process is running on.

The only module in this package that touches the system: it reads the license
and asks ``middlewared.utils.hardware`` what this machine is. Nothing else here
imports it, so the rest of the package stays pure and ``applies`` can still be
evaluated against synthesized facts.
"""

from __future__ import annotations

from middlewared.utils.hardware import get_hardware_class
from middlewared.utils.license import get_license

from .facts import AlertFacts

__all__ = ("get_alert_facts",)


def get_alert_facts() -> AlertFacts:
    """Read what this system is, right now.

    Deliberately not cached. A license can be uploaded or removed under a
    running middlewared, and an applicability answer that survives that is a bug
    -- which is exactly what ``SystemService.PRODUCT_TYPE`` was.
    """
    return AlertFacts(hardware_class=get_hardware_class(), license=get_license())
