"""Translate legacy on-disk licenses into the normalized LicenseInfo shape.

A legacy license whose model starts with "freenas" is not honoured at all:
get_legacy_license_info returns None and the system reads as unlicensed. Those
blobs were issued for FreeNAS Certified and FreeNAS Mini hardware, which bought
none of the functionality the injection below hands out, and there is no useful
subset to inject for them instead. The rejection is deliberately silent, so a
caller cannot distinguish a rejected blob from a missing one.

Every legacy license that survives that check gets the same flags injected.
Legacy licenses predate the per-feature key vocabulary, so a modern gate reading
one sees only the handful of bits the old format could carry, and an existing
holder would lose working functionality on upgrade. Each injected flag is here
because the gate it replaced already allowed it:

- APPS, VMS and CONTAINERS. Their matrix vectors deny a license that lacks the
  key, and today's gates only consult the license on HA capable hardware, so
  without these a legacy holder would lose apps and VMs on upgrade.
- STIG and TRUESEARCH, matching gates that key off any valid license regardless
  of product type.
- NFS_SNAPSHOT and NETWORK_FEC. Their matrix vectors are key-only on both
  hardware sides, so a legacy holder exposing snapshots over NFS or running a
  configured FEC mode would lose it on upgrade.
- NVMEOF_SPDK. Key-only on both hardware sides, while the gate it replaced
  granted SPDK to any HA capable system.
- RDMA. Key-only on both hardware sides, while the gate it replaced required an
  enterprise system that was not a MINI and had an RDMA capable NIC fitted. The
  NIC remains a hardware check outside the license; only the model half of that
  gate is dropped.
- KMIP and WEBSHARE. Key-only on both hardware sides and no legacy license can
  carry either key, while neither key management nor Webshare has a license gate
  at all today, so every legacy holder can already use them.
- DIRECTORY_SERVICES, which gates directory-services authentication to the UI
  and API rather than directory services themselves. Key-only on both hardware
  sides, so no legacy holder loses UI/API logins on upgrade.
- SUPPORT. Key-only on both hardware sides, and the tier a legacy license grants
  is carried by its contract type rather than by a key, so the flag is injected
  regardless of contract type and the tier is stamped onto it (see
  _support_tier).
- AUTOTUNE, CATALOG_ENTERPRISE_TRAIN, MISSION_CRITICAL, SMB_FASTPATH and
  SMB_VEEAM, the flags historically gated behind an is_enterprise check. With
  freenas models rejected outright, the only holder this widens is a legacy blob
  carrying no model at all. AUTOTUNE has no entitlement policy behind it, and
  CATALOG_ENTERPRISE_TRAIN grants on hardware plus key so it stays denied off
  appliance hardware, which leaves MISSION_CRITICAL, SMB_FASTPATH and SMB_VEEAM
  as the whole of the widening. MISSION_CRITICAL is key-only on both hardware
  sides, which is precisely what keeps a legacy holder on the Mission Critical
  update profile after upgrade.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
import logging
from types import MappingProxyType

from licenselib.license import Features, License
from licenselib.utils import proactive_support_allowed
from truenas_pylicensed import FEATURE_NAME_MAP, LicenseType
from truenas_pylicensed.features import LicenseFeature, SupportTier

from .constants import LEGACY_LICENSE_FILE, LICENSE_ADDHW_MAPPING
from .types import FeatureInfo, LicenseInfo

logger = logging.getLogger(__name__)

__all__ = (
    "get_legacy_license_info",
    "parse_legacy_license",
)


# TODO: injecting APPS overrides the legacy jails bit, granting apps to HA capable systems that never purchased it
# TODO: injecting VMS overrides the legacy vm bit, granting VMs to HA capable systems that never purchased it
_LEGACY_INJECT: frozenset[LicenseFeature] = frozenset(
    {
        LicenseFeature.APPS,
        LicenseFeature.AUTOTUNE,
        LicenseFeature.CATALOG_ENTERPRISE_TRAIN,
        LicenseFeature.CONTAINERS,
        LicenseFeature.DIRECTORY_SERVICES,
        LicenseFeature.KMIP,
        LicenseFeature.MISSION_CRITICAL,
        LicenseFeature.NETWORK_FEC,
        LicenseFeature.NFS_SNAPSHOT,
        LicenseFeature.NVMEOF_SPDK,
        LicenseFeature.RDMA,
        LicenseFeature.SMB_FASTPATH,
        LicenseFeature.SMB_VEEAM,
        LicenseFeature.STIG,
        LicenseFeature.SUPPORT,
        LicenseFeature.TRUESEARCH,
        LicenseFeature.VMS,
        LicenseFeature.WEBSHARE,
    }
)


def _support_tier(contract_type_name: str) -> str:
    """Map a legacy contract type onto the SupportTier vocabulary.

    This mapping is load-bearing. SUPPORT is injected into every legacy license
    regardless of contract type, so the tier stamped here is the only thing
    separating a legacy licensee from proactive support. Contract types outside
    the SupportTier vocabulary collapse to BRONZE, which the proactive-support
    tier gate rejects. Unconditional injection is only safe while that gate
    keeps rejecting BRONZE; a tier-blind gate over an injected SUPPORT key would
    hand proactive support to the entire legacy installed base.

    Membership is derived from SupportTier rather than listed here so a newly
    added tier cannot silently fall through to BRONZE.
    """
    try:
        return SupportTier(contract_type_name.upper()).value
    except ValueError:
        return SupportTier.BRONZE.value


@lru_cache()
def get_legacy_license_info() -> LicenseInfo | None:
    """Return a LicenseInfo built from the legacy on-disk license, or None."""
    try:
        with open(LEGACY_LICENSE_FILE) as f:
            info = parse_legacy_license(f.read().strip("\n"))
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning("Error loading legacy license: %r", e)
        return None

    if info.model is not None and info.model.lower().startswith("freenas"):
        return None

    return info


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
    enclosures = {
        LICENSE_ADDHW_MAPPING[code]: quantity for quantity, code in lic.addhw if code in LICENSE_ADDHW_MAPPING
    }
    # Iterate the enum rather than the frozenset so injected names land in declaration order.
    for feat in LicenseFeature:
        if feat in _LEGACY_INJECT and feat not in feature_names:
            feature_names.append(feat.value)

    return LicenseInfo(
        id=f"legacy_{lic.system_serial}",
        type=LicenseType.ENTERPRISE_HA if lic.system_serial_ha else LicenseType.ENTERPRISE_SINGLE,
        model=model,
        support_expires_at=lic.contract_end,
        # A legacy blob carries no per-feature dates, only the support contract's, so SUPPORT
        # is the only feature that gets dated.
        features=MappingProxyType(
            {
                name: FeatureInfo(
                    name=name,
                    start_date=lic.contract_start if name == "SUPPORT" else None,
                    expires_at=lic.contract_end if name == "SUPPORT" else None,
                    source="enterprise",
                    type=_support_tier(lic.contract_type.name) if name == "SUPPORT" else None,
                )
                for name in feature_names
            }
        ),
        serials=tuple(serials),
        enclosures=MappingProxyType(enclosures),
        contract_type=lic.contract_type.name.upper(),
    )
