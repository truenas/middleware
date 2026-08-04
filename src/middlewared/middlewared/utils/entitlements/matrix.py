from __future__ import annotations

import typing
from types import MappingProxyType

from truenas_pylicensed.features import LicenseFeature

from .engine import DerivedEntitlement, Vector

if typing.TYPE_CHECKING:
    from collections.abc import Mapping


# Reference-only feature matrix (verbatim from the product feature matrix).
# Cell order matches COLUMNS. Only a few features are wired into the live
# POLICY; the rest ship as inert reference data and flipping a feature onto its
# Vector is a data change.
TARGET_VECTORS: Mapping[LicenseFeature, Vector] = MappingProxyType(
    {
        LicenseFeature.APPS: Vector(1, 1, 0, 1, 0, 1),
        # TODO: Autotune needs fixes in the autotune script itself
        LicenseFeature.AUTOTUNE: Vector(0, 0, 0, 1, 0, 0),
        LicenseFeature.CATALOG_ENTERPRISE_TRAIN: Vector(0, 0, 0, 1, 0, 0),
        LicenseFeature.CONTAINERS: Vector(1, 1, 0, 1, 0, 1),
        LicenseFeature.DEDUP: Vector(1, 0, 0, 1, 0, 1),
        LicenseFeature.DIRECTORY_SERVICES: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.FIBRECHANNEL: Vector(0, 0, 1, 1, 0, 1),
        LicenseFeature.KMIP: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.LTS: Vector(0, 0, 1, 1, 0, 1),
        LicenseFeature.MISSION_CRITICAL: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.NETWORK_FEC: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.NFS_SNAPSHOT: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.NVMEOF_SPDK: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.RDMA: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.SED: Vector(0, 1, 1, 1, 1, 1),
        LicenseFeature.SMB_FASTPATH: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.SMB_VEEAM: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.STIG: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.SUPPORT: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.TRUESEARCH: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.VMS: Vector(1, 1, 0, 1, 0, 1),
        LicenseFeature.WEBSHARE: Vector(0, 0, 0, 1, 0, 1),
        LicenseFeature.ZFSTIER: Vector(0, 0, 0, 1, 0, 1),
    }
)

# Cells for the entitlements that are not license features, so cannot live in
# TARGET_VECTORS (which is asserted equal to LicenseFeature). Keyed by the policy key
# rather than by the feature a rule qualifies against, so that two rows which happen to
# agree today stay free to diverge.
#
# PROACTIVE_SUPPORT is the product matrix's "Proactive Support" row, corrected from
# 0,0,1,1,0,1 -- that row grants on a license alone, with no tier consulted, which is not
# what proactive support means. It has only ever looked right because the tier check
# denied a missing key before any cell was read. The spreadsheet has NOT been updated, so
# do not re-sync this row from it.
#
# HA has no entry on purpose: it is a license type, not a key, so no cell can decide it
# (see policy.py).
DERIVED_VECTORS: Mapping[DerivedEntitlement, Vector] = MappingProxyType(
    {
        DerivedEntitlement.PROACTIVE_SUPPORT: Vector(0, 0, 0, 1, 0, 1),
    }
)
