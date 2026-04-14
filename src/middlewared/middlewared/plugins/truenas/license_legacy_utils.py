from functools import lru_cache
from datetime import date

from licenselib.license import Features, License
from licenselib.utils import proactive_support_allowed
from truenas_pylicensed import LicenseType

from .license_utils import FeatureInfo, LicenseInfo


LEGACY_LICENSE_FILE = '/data/license'
LICENSE_ADDHW_MAPPING = {
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


@lru_cache()
def get_legacy_license_info() -> LicenseInfo | None:
    """Return a LicenseInfo built from the legacy on-disk license, or None."""
    try:
        with open(LEGACY_LICENSE_FILE) as f:
            return parse_legacy_license(f.read().strip('\n'))
    except Exception:
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

    feature_name_map = {"JAILS": "APPS"}
    feature_names = [feature_name_map.get(f.name.upper(), f.name.upper()) for f in features]
    if proactive_support_allowed(lic.contract_type.name):
        feature_names.append("SUPPORT")

    return LicenseInfo(
        id=f"legacy_{lic.system_serial}",
        type=LicenseType.ENTERPRISE_HA if lic.system_serial_ha else LicenseType.ENTERPRISE_SINGLE,
        model=lic.model or None,
        expires_at=lic.contract_end,
        features=[
            FeatureInfo(name=name, start_date=lic.contract_start, expires_at=lic.contract_end)
            for name in feature_names
        ],
        serials=serials,
        enclosures={
            LICENSE_ADDHW_MAPPING[code]: quantity
            for quantity, code in lic.addhw
            if code in LICENSE_ADDHW_MAPPING
        },
    )
