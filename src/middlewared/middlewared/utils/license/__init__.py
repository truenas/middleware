"""This system's license, normalized to one shape regardless of its source.

A license reaches us either from the license daemon (``daemon``) or from a
pre-daemon on-disk blob (``legacy``). Both produce the same ``LicenseInfo``,
so no consumer needs to know which one answered.

Nothing in this package may import ``middlewared.service``, so ``LicenseInfo``
stays reachable without dragging in the service framework.
"""

from __future__ import annotations

from truenas_pylicensed import LicenseError, LicenseStatus, verify

from .constants import (
    LEGACY_LICENSE_FILE,
    LICENSE_ADDHW_MAPPING,
    LICENSE_BACKUP,
    LICENSE_DIR,
    LICENSE_FILE,
)
from .daemon import from_license_status, get_fingerprint_b64, upload_license
from .legacy import get_legacy_license_info, parse_legacy_license
from .types import FeatureInfo, LicenseInfo

__all__ = [
    "LEGACY_LICENSE_FILE",
    "LICENSE_ADDHW_MAPPING",
    "LICENSE_BACKUP",
    "LICENSE_DIR",
    "LICENSE_FILE",
    "FeatureInfo",
    "LicenseInfo",
    "from_license_status",
    "get_fingerprint_b64",
    "get_legacy_license_info",
    "get_license",
    "parse_legacy_license",
    "upload_license",
]

# Codes that mean the daemon had nothing to say about a v2 license, so the
# legacy blob underneath is still the best answer available. Only NO_LICENSE
# falls back: a daemon that is unreachable or erroring reads as unlicensed
# rather than resurrecting the legacy blob.
_FALLBACK_CODES = frozenset(
    {
        LicenseError.NO_LICENSE,
    }
)


def get_license(status: LicenseStatus | None = None) -> LicenseInfo | None:
    """Return this system's license, or None if it has none.

    A v2 license that exists but fails verification is authoritative: return None
    rather than resurrecting the legacy blob underneath it.
    """
    if status is None:
        status = verify()

    if status.code in _FALLBACK_CODES:
        return get_legacy_license_info()

    return from_license_status(status)
