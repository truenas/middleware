from truenas_pydmi import legacy_dmi_info

# SMBIOS prefixes burned in by production for each iX platform.
# z, x, m (incl. current minis), f, h, r, v, freenas-mini.
PLATFORM_PREFIXES = (
    "TRUENAS-Z",
    "TRUENAS-X",
    "TRUENAS-M",
    "TRUENAS-F",
    "TRUENAS-H",
    "TRUENAS-R",
    "TRUENAS-V",
    "FREENAS-MINI",
)
TRUENAS_UNKNOWN = "TRUENAS-UNKNOWN"


def get_chassis_hardware() -> str:
    dmi = legacy_dmi_info()
    if dmi.system_product_name.startswith(PLATFORM_PREFIXES):
        return dmi.system_product_name
    if dmi.baseboard_product_name == "iXsystems TrueNAS X10":
        # production may not have burned in the x-series model string
        return "TRUENAS-X"
    return TRUENAS_UNKNOWN
