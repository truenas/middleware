"""Translate legacy on-disk licenses into the normalized LicenseInfo shape.

Legacy licenses predate the per-feature key vocabulary, so the flags a modern
system expects are injected here from the contract's type and model. The
injection buckets mirror how today's gates read a legacy license:

- co-injected bits: APPS holders also get CONTAINERS, which was never a
  separate legacy bit.
- every legacy license (including freenascertified): STIG and TRUESEARCH,
  matching gates that key off any valid license regardless of product type.
- enterprise models only (model present and not freenas-prefixed, the same
  demotion rule product_type applies): the flags historically gated behind an
  is_enterprise check.
"""
from functools import lru_cache
from datetime import date
import logging
from collections.abc import Mapping
from types import MappingProxyType

from licenselib.license import Features, License
from licenselib.utils import proactive_support_allowed
from truenas_pylicensed import FEATURE_NAME_MAP, LicenseType
from truenas_pylicensed.features import LicenseFeature

from .license_utils import FeatureInfo, LicenseInfo

logger = logging.getLogger(__name__)


_BIT_COINJECT: Mapping[LicenseFeature, frozenset[LicenseFeature]] = MappingProxyType({
    LicenseFeature.APPS: frozenset({LicenseFeature.CONTAINERS}),
})
_ALL_LEGACY_INJECT: frozenset[LicenseFeature] = frozenset({LicenseFeature.STIG, LicenseFeature.TRUESEARCH})
_ENT_ONLY_INJECT: frozenset[LicenseFeature] = frozenset({
    LicenseFeature.RDMA, LicenseFeature.SMB_VEEAM, LicenseFeature.SMB_FASTPATH,
    LicenseFeature.DIRECTORY_SERVICES, LicenseFeature.NETWORK_FEC, LicenseFeature.MISSION_CRITICAL,
    LicenseFeature.AUTOTUNE, LicenseFeature.NVMEOF_SPDK, LicenseFeature.CATALOG_ENTERPRISE_TRAIN,
    LicenseFeature.NFS_SNAPSHOT,
})


LEGACY_LICENSE_FILE = '/data/license'
LICENSE_ADDHW_MAPPING = MappingProxyType({
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
})


@lru_cache()
def get_legacy_license_info() -> LicenseInfo | None:
    """Return a LicenseInfo built from the legacy on-disk license, or None."""
    try:
        with open(LEGACY_LICENSE_FILE) as f:
            return parse_legacy_license(f.read().strip('\n'))
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
    for flag, coinjected in _BIT_COINJECT.items():
        if flag in feature_names:
            injected |= coinjected
    if model is not None and not model.lower().startswith("freenas"):
        injected |= _ENT_ONLY_INJECT
    for feat in LicenseFeature:
        if feat in injected and feat not in feature_names:
            feature_names.append(feat.value)

    return LicenseInfo(
        id=f"legacy_{lic.system_serial}",
        type=LicenseType.ENTERPRISE_HA if lic.system_serial_ha else LicenseType.ENTERPRISE_SINGLE,
        model=model,
        expires_at=lic.contract_end,
        features=[
            FeatureInfo(
                name=name,
                start_date=lic.contract_start,
                expires_at=lic.contract_end,
                source="enterprise",
                type=lic.contract_type.name.upper() if name == "SUPPORT" else None,
            )
            for name in feature_names
        ],
        serials=serials,
        enclosures={
            LICENSE_ADDHW_MAPPING[code]: quantity
            for quantity, code in lic.addhw
            if code in LICENSE_ADDHW_MAPPING
        },
        contract_type=lic.contract_type.name.upper(),
    )
