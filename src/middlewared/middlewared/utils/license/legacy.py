"""Translate legacy on-disk licenses into the normalized LicenseInfo shape.

Legacy licenses predate the per-feature key vocabulary, so the flags a modern
system expects are injected here from the contract's type and model. The
injection buckets mirror how today's gates read a legacy license:

- every legacy license (including freenascertified): STIG and TRUESEARCH,
  matching gates that key off any valid license regardless of product type.
- every legacy license: APPS, VMS and CONTAINERS. Their matrix vectors deny a
  license that lacks the key, and today's gates only consult the license on
  HA capable hardware, so without these a legacy holder would lose apps and
  VMs on upgrade.
- every legacy license: NFS_SNAPSHOT. Its matrix vector is key-only on both
  hardware sides, so any legacy holder exposing snapshots over NFS would lose
  the export on upgrade unless the flag is injected regardless of model.
- every legacy license: NVMEOF_SPDK. Its matrix vector is key-only on both
  hardware sides, while the gate it replaced granted SPDK to any HA capable
  system, so the flag is injected regardless of model.
- every legacy license: NETWORK_FEC. Its matrix vector is key-only on both
  hardware sides, so any legacy holder configuring FEC mode would lose it on
  upgrade unless the flag is injected regardless of model.
- every legacy license: RDMA. Its matrix vector is key-only on both hardware
  sides, while the gate it replaced required an enterprise system that was not
  a MINI and had an RDMA capable NIC fitted. The NIC remains a hardware check
  outside the license, but the model half of that gate is dropped, so the flag
  is injected regardless of model to keep every legacy holder with the hardware
  able to use RDMA.
- enterprise models only (model present and not freenas-prefixed, the same
  demotion rule product_type applies): the flags historically gated behind an
  is_enterprise check.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
import logging
from types import MappingProxyType

from licenselib.license import Features, License
from licenselib.utils import proactive_support_allowed
from truenas_pylicensed import FEATURE_NAME_MAP, LicenseType
from truenas_pylicensed.features import LicenseFeature

from .constants import LEGACY_LICENSE_FILE, LICENSE_ADDHW_MAPPING
from .types import FeatureInfo, LicenseInfo

logger = logging.getLogger(__name__)

__all__ = (
    "get_legacy_license_info",
    "parse_legacy_license",
)


# TODO: injecting APPS overrides the legacy jails bit, granting apps to HA capable systems that never purchased it
# TODO: injecting VMS overrides the legacy vm bit, granting VMs to HA capable systems that never purchased it
_ALL_LEGACY_INJECT: frozenset[LicenseFeature] = frozenset({
    LicenseFeature.STIG, LicenseFeature.TRUESEARCH, LicenseFeature.APPS, LicenseFeature.VMS,
    LicenseFeature.CONTAINERS, LicenseFeature.NFS_SNAPSHOT, LicenseFeature.NVMEOF_SPDK,
    LicenseFeature.NETWORK_FEC, LicenseFeature.RDMA,
})
_ENT_ONLY_INJECT: frozenset[LicenseFeature] = frozenset({
    LicenseFeature.SMB_VEEAM, LicenseFeature.SMB_FASTPATH,
    LicenseFeature.DIRECTORY_SERVICES, LicenseFeature.MISSION_CRITICAL,
    LicenseFeature.AUTOTUNE, LicenseFeature.CATALOG_ENTERPRISE_TRAIN,
})


@lru_cache()
def get_legacy_license_info() -> LicenseInfo | None:
    """Return a LicenseInfo built from the legacy on-disk license, or None."""
    try:
        with open(LEGACY_LICENSE_FILE) as f:
            return parse_legacy_license(f.read().strip("\n"))
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning("Error loading legacy license: %r", e)
        return None


def parse_legacy_license(text: str) -> LicenseInfo:
    lic = License.load(text)

    serials = [lic.system_serial]
    if lic.system_serial_ha:
        serials.append(lic.system_serial_ha)

    features = list(lic.features)
    if Features.fibrechannel not in lic.features and lic.contract_start < date(2017, 4, 14):
        # Licenses issued before 2017-04-14 had a bug in the feature bit for fibrechannel, which
        # means they were issued having dedup+jails instead.
        if Features.dedup in lic.features and Features.jails in lic.features:
            features.append(Features.fibrechannel)

    feature_names: list[str] = [str(FEATURE_NAME_MAP.get(f.name.upper(), f.name.upper())) for f in features]
    if proactive_support_allowed(lic.contract_type.name):
        feature_names.append("SUPPORT")

    model = lic.model or None
    injected: set[LicenseFeature] = set(_ALL_LEGACY_INJECT)
    if model is not None and not model.lower().startswith("freenas"):
        injected |= _ENT_ONLY_INJECT
    for feat in LicenseFeature:
        if feat in injected and feat not in feature_names:
            feature_names.append(feat.value)

    return LicenseInfo(
        id=f"legacy_{lic.system_serial}",
        type=LicenseType.ENTERPRISE_HA if lic.system_serial_ha else LicenseType.ENTERPRISE_SINGLE,
        model=model,
        support_expires_at=lic.contract_end,
        license_expires_at=None,
        features=MappingProxyType({
            name: FeatureInfo(
                name=name,
                start_date=lic.contract_start,
                expires_at=lic.contract_end,
                source="enterprise",
                type=lic.contract_type.name.upper() if name == "SUPPORT" else None,
            )
            for name in feature_names
        }),
        serials=tuple(serials),
        enclosures=MappingProxyType({
            LICENSE_ADDHW_MAPPING[code]: quantity
            for quantity, code in lic.addhw
            if code in LICENSE_ADDHW_MAPPING
        }),
        contract_type=lic.contract_type.name.upper(),
    )
