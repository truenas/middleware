"""Translate legacy on-disk licenses into the normalized LicenseInfo shape.

Legacy licenses predate the per-feature key vocabulary, so a modern gate reading
one would see almost no keys and revoke functionality the holder already has.
Every surviving legacy blob therefore gets _LEGACY_INJECT granted outright.

A blob whose model starts with "freenas" bought none of that functionality, so it
is rejected entirely and the system reads as unlicensed. The rejection is silent:
a caller cannot distinguish a rejected blob from a missing one.
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
    tier gate rejects.

    Membership is derived from SupportTier rather than listed here so a newly
    added tier cannot silently fall through to BRONZE.
    """
    try:
        return SupportTier(contract_type_name.upper()).value
    except ValueError:
        return SupportTier.BRONZE.value


@lru_cache()
def get_legacy_license_info() -> LicenseInfo | None:
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
        # A legacy blob carries only the support contract's dates, not per-feature ones.
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
