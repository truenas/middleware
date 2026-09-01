from __future__ import annotations

import typing
from types import MappingProxyType

from truenas_pylicensed.features import LicenseFeature

from .engine import DerivedEntitlement, Vector

if typing.TYPE_CHECKING:
    from collections.abc import Mapping


TARGET_VECTORS: Mapping[LicenseFeature, Vector] = MappingProxyType(
    {
        LicenseFeature.APPS: Vector(ce=1, hw=1, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        # TODO: Autotune needs fixes in the autotune script itself
        LicenseFeature.AUTOTUNE: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=0),
        LicenseFeature.CATALOG_ENTERPRISE_TRAIN: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=0),
        LicenseFeature.CONTAINERS: Vector(ce=1, hw=1, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.DEDUP: Vector(ce=1, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.DIRECTORY_SERVICES: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.FIBRECHANNEL: Vector(ce=0, hw=0, hw_l=1, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.KMIP: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.MISSION_CRITICAL: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.NETWORK_FEC: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.NFS_SNAPSHOT: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.NVMEOF_SPDK: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.RDMA: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.SED: Vector(ce=0, hw=1, hw_l=1, hw_k=1, ce_l=1, ce_k=1),
        LicenseFeature.SMB_FASTPATH: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.SMB_VEEAM: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.STIG: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.SUPPORT: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.TRUESEARCH: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.VMS: Vector(ce=1, hw=1, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.WEBSHARE: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
        LicenseFeature.ZFSTIER: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
    }
)

# HA has no entry on purpose: it is a license type, not a key, so no cell can decide it.
DERIVED_VECTORS: Mapping[DerivedEntitlement, Vector] = MappingProxyType(
    {
        DerivedEntitlement.PROACTIVE_SUPPORT: Vector(ce=0, hw=0, hw_l=0, hw_k=1, ce_l=0, ce_k=1),
    }
)
