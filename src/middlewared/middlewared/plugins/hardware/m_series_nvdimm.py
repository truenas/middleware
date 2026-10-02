from __future__ import annotations

import functools
import os
import stat
import struct
from typing import TypedDict

from middlewared.service import Service
from middlewared.utils.hardware import nvdimm

# Names of the bits in each status value, lowest bit first
CRITICAL_HEALTH = (
    "PERSISTENCY_LOST_ERROR",
    "WARNING_THRESHOLD_EXCEEDED",
    "PERSISTENCY_RESTORED",
    "BELOW_WARNING_THRESHOLD",
    "PERMANENT_HARDWARE_FAILURE",
    "EVENT_N_LOW",
)
MODULE_HEALTH = (
    "VOLTAGE_REGULATOR_FAILED",
    "VDD_LOST",
    "VPP_LOST",
    "VTT_LOST",
    "DRAM_NOT_SELF_REFRESH",
    "CONTROLLER_HARDWARE_ERROR",
    "NVM_CONTROLLER_ERROR",
    "NVM_LIFETIME_ERROR",
    "NOT_ENOUGH_ENERGY_FOR_CSAVE",
    "INVALID_FIRMWARE_ERROR",
    "CONFIG_DATA_ERROR",
    "NO_ES_PRESENT",
    "ES_POLICY_NOT_SET",
    "ES_HARDWARE_FAILURE",
    "ES_HEALTH_ASSESSMENT_ERROR",
)
ERROR_THRESHOLD = ("NVM_LIFETIME_ERROR", "ES_LIFETIME_ERROR", "ES_TEMP_ERROR")
# ixnvdimm tests the lowest bit for all three of these names. These are the bits it meant.
WARNING_THRESHOLD = ("NVM_LIFETIME_WARNING", "ES_LIFETIME_WARNING", "ES_TEMP_WARNING")


class HealthInfo(TypedDict):
    critical_health_info: dict[str, list[str]]
    nvm_health_info: dict[str, list[str]]
    nvm_error_threshold_status: dict[str, list[str]]
    nvm_warning_threshold_status: dict[str, list[str]]
    nvm_lifetime: str
    nvm_temperature: str
    es_lifetime: str
    es_temperature: str


class VendorInfo(TypedDict):
    vendor: str | None
    device: str | None
    rev_id: str | None
    subvendor: str | None
    subdevice: str | None
    subrev_id: str | None
    part_num: str | None
    size: str | None
    clock_speed: str | None
    qualified_firmware: list[str]
    recommended_firmware: str | None


@functools.cache
def static_info(dev_path: str) -> tuple[int, str | None]:
    """Return the specification revision and running firmware version of an NVDIMM.

    The result is cached per device for the life of the process. These values only
    change when the module restarts, and we do not support hot-plugging NVDIMMs, so
    a device path always refers to the same module. Caching them saves three firmware
    requests on every alert check, and each request is one that can fail when kernel
    memory is fragmented.

    The firmware version is ``None`` when the module reports no usable running slot or
    version. A failed read raises ``OSError`` and is not cached, so the next call retries.
    """
    # The kernel refuses these requests on a descriptor opened read-only
    with open(dev_path, "r+b", buffering=0) as f:
        fd = f.fileno()
        specrev = nvdimm.i2c_read(fd, *nvdimm.SPECREV)
        running_firmware = None
        running_slot = nvdimm.i2c_read(fd, *nvdimm.FW_SLOT_INFO) >> 4
        if running_slot < len(nvdimm.SLOT_FWREV_HIGH):
            major, minor = divmod(nvdimm.i2c_read(fd, *nvdimm.SLOT_FWREV_HIGH[running_slot]), 16)
            if major <= 9 and minor <= 9:
                running_firmware = f"{major}.{minor}"

    # 0x22 is revision 2.2, which the alert compares as 22
    return specrev // 16 * 10 + specrev % 16, running_firmware


def bit_names(value: int, names: tuple[str, ...], width: int) -> dict[str, list[str]]:
    return {f"0x{value:0{width}x}": [name for bit, name in enumerate(names) if value >> bit & 1]}


def vendor_info(dev: str) -> VendorInfo:
    mapping: dict[str, VendorInfo] = {
        "0x2c80_0x4e32_0x31_0x3480_0x4131_0x01": {
            "vendor": "0x2c80",
            "device": "0x4e32",
            "rev_id": "0x31",
            "subvendor": "0x3480",
            "subdevice": "0x4131",
            "subrev_id": "0x01",
            "part_num": "18ASF2G72PF12G6V21AB",
            "size": "16GB",
            "clock_speed": "2666MHz",
            "qualified_firmware": ["2.6"],
            "recommended_firmware": "2.6",
        },
        "0x2c80_0x4e36_0x31_0x3480_0x4231_0x02": {
            "vendor": "0x2c80",
            "device": "0x4e36",
            "rev_id": "0x31",
            "subvendor": "0x3480",
            "subdevice": "0x4231",
            "subrev_id": "0x02",
            "part_num": "18ASF2G72PF12G9WP1AB",
            "size": "16GB",
            "clock_speed": "2933MHz",
            "qualified_firmware": ["2.2"],
            "recommended_firmware": "2.2",
        },
        "0x2c80_0x4e33_0x31_0x3480_0x4231_0x01": {
            "vendor": "0x2c80",
            "device": "0x4e33",
            "rev_id": "0x31",
            "subvendor": "0x3480",
            "subdevice": "0x4231",
            "subrev_id": "0x01",
            "part_num": "36ASS4G72PF12G9PR1AB",
            "size": "32GB",
            "clock_speed": "2933MHz",
            "qualified_firmware": ["2.4"],
            "recommended_firmware": "2.4",
        },
        "0xce01_0x4e38_0x33_0xc180_0x4331_0x01": {
            "vendor": "0xce01",
            "device": "0x4e38",
            "rev_id": "0x33",
            "subvendor": "0xc180",
            "subdevice": "0x4331",
            "subrev_id": "0x01",
            "part_num": "AGIGA8811-016ACA",
            "size": "16GB",
            "clock_speed": "2933MHz",
            "qualified_firmware": ["0.8"],
            "recommended_firmware": "0.8",
        },
        "0xce01_0x4e42_0x31_0xc180_0x4331_0x01": {
            "vendor": "0xce01",
            "device": "0x4e42",
            "rev_id": "0x31",
            "subvendor": "0xc180",
            "subdevice": "0x4331",
            "subrev_id": "0x01",
            "part_num": "AGIGA8811-016BCA",
            "size": "16GB",
            "clock_speed": "2933MHz",
            "qualified_firmware": ["3.0"],
            "recommended_firmware": "3.0",
        },
        "0xce01_0x4e39_0x34_0xc180_0x4331_0x01": {
            "vendor": "0xce01",
            "device": "0x4e39",
            "rev_id": "0x34",
            "subvendor": "0xc180",
            "subdevice": "0x4331",
            "subrev_id": "0x01",
            "part_num": "AGIGA8811-032ACA",
            "size": "32GB",
            "clock_speed": "2933MHz",
            "qualified_firmware": ["0.8"],
            "recommended_firmware": "0.8",
        },
        "unknown": {
            "vendor": None,
            "device": None,
            "rev_id": None,
            "subvendor": None,
            "subdevice": None,
            "subrev_id": None,
            "part_num": None,
            "size": None,
            "clock_speed": None,
            "qualified_firmware": [],
            "recommended_firmware": None,
        },
    }
    # sysfs shows each id with its two bytes swapped relative to the keys above
    ids: list[int] = []
    for attr in ("vendor", "device", "rev_id", "subsystem_vendor", "subsystem_device", "subsystem_rev_id"):
        with open(f"/sys/bus/nd/devices/{dev}/nfit/{attr}") as f:
            value = int(f.read().strip(), 0)
            ids.append(int.from_bytes(value.to_bytes(2, "little"), "big"))

    return mapping.get("0x%04x_0x%04x_0x%02x_0x%04x_0x%04x_0x%02x" % tuple(ids), mapping["unknown"])


def health_info(fd: int) -> HealthInfo:
    critical = nvdimm.dsm(fd, nvdimm.CRITICAL_HEALTH)[0]
    health, temperature, error, warning, lifetime = struct.unpack_from(
        "<HHBBb", nvdimm.dsm(fd, nvdimm.MODULE_HEALTH, need=7)
    )
    es_lifetime, es_temperature = struct.unpack_from("<bH", nvdimm.dsm(fd, nvdimm.ES_HEALTH, need=3))
    # Workaround wrong units reported by Micron NVDIMMs, as ixnvdimm does
    if es_temperature & 0x1000:
        es_temperature = -((es_temperature & 0x0FFF) // 16)
    elif es_temperature >= 128:
        es_temperature = (es_temperature & 0x0FFF) // 16

    return {
        "critical_health_info": bit_names(critical, CRITICAL_HEALTH, 2),
        "nvm_health_info": bit_names(health, MODULE_HEALTH, 4),
        "nvm_error_threshold_status": bit_names(error, ERROR_THRESHOLD, 2),
        "nvm_warning_threshold_status": bit_names(warning, WARNING_THRESHOLD, 2),
        "nvm_lifetime": f"{lifetime}%",
        "nvm_temperature": str(temperature),
        "es_lifetime": f"{es_lifetime}%",
        "es_temperature": str(es_temperature),
    }


def state_flags(nmem: str) -> list[str]:
    try:
        with open(f"/sys/bus/nd/devices/{nmem.removeprefix('/dev/')}/nfit/flags") as f:
            flags = f.read().strip().split()
    except Exception:
        flags = []

    return flags


class MseriesNvdimmService(Service):
    class Config:
        private = True
        namespace = "mseries.nvdimm"

    def info(self):
        """Raises ``OSError`` when an NVDIMM cannot be read."""
        results = []
        sys = ("TRUENAS-M40", "TRUENAS-M50", "TRUENAS-M60")
        if not self.middleware.call_sync("truenas.get_chassis_hardware").startswith(sys):
            return results

        with os.scandir("/dev/") as sdir:
            for i in sdir:
                # /dev/nmemX is a character device, which is_file() does not count as a file
                if i.name.startswith("nmem") and stat.S_ISCHR(i.stat().st_mode):
                    try:
                        specrev, running_firmware = static_info(i.path)
                        # The kernel refuses these requests on a descriptor opened read-only
                        with open(i.path, "r+b", buffering=0) as f:
                            health = health_info(f.fileno())

                        vendor = vendor_info(i.name)
                    except OSError:
                        self.logger.warning("%s: failed to read NVDIMM health", i.name, exc_info=True)
                        raise

                    results.append(
                        {
                            "index": int(i.name[len("nmem")]),
                            "dev": i.name,
                            "dev_path": i.path,
                            "specrev": specrev,
                            "state_flags": state_flags(i.path),
                            **health,
                            **vendor,
                            "running_firmware": running_firmware,
                            "old_bios": running_firmware is None,
                        }
                    )

        return results
