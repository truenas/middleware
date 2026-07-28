"""On-disk locations and issuer vocabulary shared by both license sources."""

from __future__ import annotations

from types import MappingProxyType

__all__ = (
    "LEGACY_LICENSE_FILE",
    "LICENSE_ADDHW_MAPPING",
    "LICENSE_BACKUP",
    "LICENSE_DIR",
    "LICENSE_FILE",
)

LICENSE_DIR = "/data/subsystems/truenas_license"
LICENSE_FILE = f"{LICENSE_DIR}/license"
LICENSE_BACKUP = f"{LICENSE_DIR}/license.bak"

LEGACY_LICENSE_FILE = "/data/license"

LICENSE_ADDHW_MAPPING = MappingProxyType(
    {
        1: "E16",
        2: "E24",
        3: "E60",
        4: "ES60",
        5: "ES12",
        6: "ES24",
        7: "ES24F",
        8: "ES60S",
        9: "ES102",
        10: "ES102G2",
        11: "ES60G2",
        12: "ES24N",
        13: "ES60G3",
    }
)
