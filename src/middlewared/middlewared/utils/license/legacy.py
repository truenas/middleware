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
from enum import StrEnum
import errno
from functools import lru_cache
import logging
from types import MappingProxyType
from typing import Any, Final

from licenselib.license import Features, License
from licenselib.utils import proactive_support_allowed
from truenas_pylicensed import FEATURE_NAME_MAP, LicenseType
from truenas_pylicensed.features import LicenseFeature, SupportTier

from .constants import LEGACY_LICENSE_FILE, LICENSE_ADDHW_MAPPING
from .types import FeatureInfo, LicenseInfo

logger = logging.getLogger(__name__)

__all__ = (
    "HW_ONLY_MARKER",
    "LegacyStatus",
    "describe_legacy_license",
    "get_legacy_license_info",
    "legacy_license_fields",
    "parse_legacy_license",
)


class LegacyStatus(StrEnum):
    NOT_PRESENT = "NOT_PRESENT"
    READ_ERROR = "READ_ERROR"
    MALFORMED = "MALFORMED"
    REJECTED_FREENAS_MODEL = "REJECTED_FREENAS_MODEL"
    DECODED = "DECODED"


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

HW_ONLY_MARKER: Final[str] = "TRUENAS-HW-ONLY-V1"

# Reproduces the bare TRUENAS_HW entitlement column: what an iX chassis carries on the
# strength of the hardware alone, with no support contract behind it. Deliberately not a
# subset of _LEGACY_INJECT -- SED is a bitmask feature a real blob could carry, so it was
# never among the names injected into one.
_HW_ONLY_INJECT: frozenset[LicenseFeature] = frozenset(
    {
        LicenseFeature.APPS,
        LicenseFeature.CONTAINERS,
        LicenseFeature.SED,
        LicenseFeature.VMS,
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


def _is_freenas_model(model: str | None) -> bool:
    return model is not None and model.lower().startswith("freenas")


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

    if _is_freenas_model(info.model):
        return None

    return info


def legacy_license_fields(lic: Any) -> dict[str, Any]:
    """Project a decoded license onto the fields a debug bundle may carry.

    An allowlist so that a field added to ``License`` upstream cannot arrive here by default:
    it carries ``customer_name`` and ``customer_key``. ``licenselib`` is untyped, hence ``Any``.
    """
    contract_type = lic.contract_type
    return {
        "version": lic.version,
        "model": lic.model or None,
        "system_serial": lic.system_serial or None,
        "system_serial_ha": lic.system_serial_ha or None,
        # ``License.load`` leaves the raw byte in place when it matches no ContractType member.
        "contract_type": {
            "value": getattr(contract_type, "value", contract_type),
            "name": getattr(contract_type, "name", None),
        },
        "contract_start": lic.contract_start.isoformat(),
        "contract_end": lic.contract_end.isoformat(),
        "features": [feature.name for feature in lic.features],
        "addhw": [list(entry) for entry in lic.addhw],
        "hw_only": lic.customer_key == HW_ONLY_MARKER,
    }


def describe_legacy_license(path: str = LEGACY_LICENSE_FILE) -> dict[str, Any]:
    """Report the on-disk legacy license as it actually is.

    Uncached, and separate from ``get_legacy_license_info``, which answers ``None`` for an
    absent, an unreadable, a malformed and a rejected blob alike. A rejected blob is reported
    with its fields: that is the case where a system lost functionality it used to have.
    """
    try:
        with open(path) as f:
            text = f.read().strip("\n")
    except FileNotFoundError:
        return {"status": LegacyStatus.NOT_PRESENT.value, "error": None, "fields": None}
    except OSError as e:
        code = e.errno
        return {
            "status": LegacyStatus.READ_ERROR.value,
            "error": errno.errorcode.get(code, str(code)) if code is not None else None,
            "fields": None,
        }

    try:
        lic = License.load(text)
        fields = legacy_license_fields(lic)
    except Exception as e:
        # Neither the blob nor `lic` may reach this string: a License repr carries customer_key.
        return {"status": LegacyStatus.MALFORMED.value, "error": f"{type(e).__name__}: {e}", "fields": None}

    status = LegacyStatus.REJECTED_FREENAS_MODEL if _is_freenas_model(fields["model"]) else LegacyStatus.DECODED
    return {"status": status.value, "error": None, "fields": fields}


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
    if lic.customer_key == HW_ONLY_MARKER:
        # Replaces the list rather than extending it: the bitmask-derived names and the
        # conditional SUPPORT append both already happened above, and replacing is what
        # holds a marked record to the bare hardware set.
        feature_names = [f.value for f in LicenseFeature if f in _HW_ONLY_INJECT]
    else:
        # Iterate the enum rather than the frozenset so injected names land in declaration order.
        for feat in LicenseFeature:
            if feat in _LEGACY_INJECT and feat not in feature_names:
                feature_names.append(feat.value)

    return LicenseInfo(
        id=f"legacy_{lic.system_serial}",
        type=LicenseType.ENTERPRISE_HA if lic.system_serial_ha else LicenseType.ENTERPRISE_SINGLE,
        model=model,
        # A marked record has no support contract behind it, so it carries no expiry to act on.
        support_expires_at=None if lic.customer_key == HW_ONLY_MARKER else lic.contract_end,
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
