from __future__ import annotations

from dataclasses import dataclass
import glob
import logging
import re
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from middlewared.main import Middleware

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class NvdimmInfo:
    index: int
    dev: str
    dev_path: str
    specrev: int
    state_flags: list[str]
    critical_health_info: dict[str, list[str]]
    nvm_health_info: dict[str, list[str]]
    nvm_error_threshold_status: dict[str, list[str]]
    nvm_warning_threshold_status: dict[str, list[str]]
    nvm_lifetime: str | None
    nvm_temperature: str | None
    es_lifetime: str | None
    es_temperature: str | None
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
    running_firmware: str | None
    old_bios: bool


def run_ixnvdimm(nvmem_dev: str) -> tuple[str, str]:
    out = subprocess.run(
        ["ixnvdimm", nvmem_dev],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="ignore",
    ).stdout
    specrev = subprocess.run(
        ['ixnvdimm', '-r', nvmem_dev, 'SPECREV'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="ignore",
    ).stdout

    return out, specrev


def get_running_firmware_vers_and_detect_old_bios(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {'running_firmware': None, 'old_bios': True}
    if m := re.search(r"selected: [0-9]+ running: ([0-9]+)", output):
        running_slot = int(m.group(1))
        if m := re.search(rf"slot{running_slot}: ([0-9])([0-9])", output):
            result['running_firmware'] = f"{m.group(1)}.{m.group(2)}"
            result['old_bios'] = False

    return result


def get_module_health(output: str) -> str | None:
    if (m := re.search(r"Module Health:[^\n]+", output)):
        return m.group().split("Module Health: ")[-1].strip()

    return None


def vendor_info(output: str) -> dict[str, Any]:
    mapping: dict[str, dict[str, Any]] = {
        '0x2c80_0x4e32_0x31_0x3480_0x4131_0x01': {
            'vendor': '0x2c80', 'device': '0x4e32', 'rev_id': '0x31',
            'subvendor': '0x3480', 'subdevice': '0x4131', 'subrev_id': '0x01',
            'part_num': '18ASF2G72PF12G6V21AB',
            'size': '16GB', 'clock_speed': '2666MHz',
            'qualified_firmware': ['2.6'],
            'recommended_firmware': '2.6',
        },
        '0x2c80_0x4e36_0x31_0x3480_0x4231_0x02': {
            'vendor': '0x2c80', 'device': '0x4e36', 'rev_id': '0x31',
            'subvendor': '0x3480', 'subdevice': '0x4231', 'subrev_id': '0x02',
            'part_num': '18ASF2G72PF12G9WP1AB',
            'size': '16GB', 'clock_speed': '2933MHz',
            'qualified_firmware': ['2.2'],
            'recommended_firmware': '2.2',
        },
        '0x2c80_0x4e33_0x31_0x3480_0x4231_0x01': {
            'vendor': '0x2c80', 'device': '0x4e33', 'rev_id': '0x31',
            'subvendor': '0x3480', 'subdevice': '0x4231', 'subrev_id': '0x01',
            'part_num': '36ASS4G72PF12G9PR1AB',
            'size': '32GB', 'clock_speed': '2933MHz',
            'qualified_firmware': ['2.4'],
            'recommended_firmware': '2.4',
        },
        '0xce01_0x4e38_0x33_0xc180_0x4331_0x01': {
            'vendor': '0xce01', 'device': '0x4e38', 'rev_id': '0x33',
            'subvendor': '0xc180', 'subdevice': '0x4331', 'subrev_id': '0x01',
            'part_num': 'AGIGA8811-016ACA',
            'size': '16GB', 'clock_speed': '2933MHz',
            'qualified_firmware': ['0.8'],
            'recommended_firmware': '0.8',
        },
        '0xce01_0x4e42_0x31_0xc180_0x4331_0x01': {
            'vendor': '0xce01', 'device': '0x4e42', 'rev_id': '0x31',
            'subvendor': '0xc180', 'subdevice': '0x4331', 'subrev_id': '0x01',
            'part_num': 'AGIGA8811-016BCA',
            'size': '16GB', 'clock_speed': '2933MHz',
            'qualified_firmware': ['3.0'],
            'recommended_firmware': '3.0',
        },
        '0xce01_0x4e39_0x34_0xc180_0x4331_0x01': {
            'vendor': '0xce01', 'device': '0x4e39', 'rev_id': '0x34',
            'subvendor': '0xc180', 'subdevice': '0x4331', 'subrev_id': '0x01',
            'part_num': 'AGIGA8811-032ACA',
            'size': '32GB', 'clock_speed': '2933MHz',
            'qualified_firmware': ['0.8'],
            'recommended_firmware': '0.8',
        },
        'unknown': {
            'vendor': None, 'device': None, 'rev_id': None,
            'subvendor': None, 'subdevice': None, 'subrev_id': None,
            'part_num': None,
            'size': None, 'clock_speed': None,
            'qualified_firmware': [],
            'recommended_firmware': None,
        }
    }
    result = mapping['unknown']
    vend_key = subvend_key = None
    if (match := re.search(r'vendor: (?P<v>\w+) device: (?P<d>\w+) revision: (?P<r>\w+)', output)):
        vend_key = '_'.join([f'0x{v}' for v in match.groupdict().values()])

    if (match := re.search(r'subvendor: (?P<v>\w+) subdevice: (?P<d>\w+) subrevision: (?P<r>\w+)', output)):
        subvend_key = '_'.join([f'0x{v}' for v in match.groupdict().values()])

    if all((vend_key, subvend_key)):
        result = mapping.get(f'{vend_key}_{subvend_key}', mapping['unknown'])

    return result


def health_info(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        'critical_health_info': {},
        'nvm_health_info': {},
        'nvm_error_threshold_status': {},
        'nvm_warning_threshold_status': {},
        'nvm_lifetime': None,
        'nvm_temperature': None,
        'es_lifetime': None,
        'es_temperature': None,
    }
    if m := re.search(r'Critical Health Info: (.*)', output):
        bit, vals = m.group(1).split(' ', 1)
        result['critical_health_info'][bit] = [i for i in vals.lstrip('<').rstrip('>').split(',') if i]
    if m := re.search(r'Module Health: (.*)', output):
        bit, vals = m.group(1).split(' ', 1)
        result['nvm_health_info'][bit] = [i for i in vals.lstrip('<').rstrip('>').split(',') if i]
    if m := re.search(r'Error Threshold Status: (.*)', output):
        bit, vals = m.group(1).split(' ', 1)
        result['nvm_error_threshold_status'][bit] = [i for i in vals.lstrip('<').rstrip('>').split(',') if i]
    if m := re.search(r'Warning Threshold Status: (.*)', output):
        bit, vals = m.group(1).split(' ', 1)
        result['nvm_warning_threshold_status'][bit] = [i for i in vals.lstrip('<').rstrip('>').split(',') if i]
    if m := re.search(r'NVM Lifetime: (.*)', output):
        result['nvm_lifetime'] = m.group(1).split(' ', 1)[0]
    if m := re.search(r'Module Current Temperature: (.*)', output):
        result['nvm_temperature'] = m.group(1).split(' ', 1)[0]
    if m := re.search(r'ES Lifetime Percentage: (.*)', output):
        result['es_lifetime'] = m.group(1).split(' ', 1)[0]
    if m := re.search(r'ES Current Temperature: (.*)', output):
        result['es_temperature'] = m.group(1).split(' ', 1)[0]

    return result


def state_flags(nmem: str) -> list[str]:
    try:
        with open(f'/sys/bus/nd/devices/{nmem.removeprefix("/dev/")}/nfit/flags') as f:
            flags = f.read().strip().split()
    except Exception:
        flags = []

    return flags


def info(middleware: Middleware) -> list[NvdimmInfo]:
    results: list[NvdimmInfo] = []
    sys = ("TRUENAS-M40", "TRUENAS-M50", "TRUENAS-M60")
    if not middleware.call_sync("truenas.get_chassis_hardware").startswith(sys):
        return results

    try:
        for nmem in glob.glob("/dev/nmem*"):
            output, specrev = run_ixnvdimm(nmem)

            entry: dict[str, Any] = {
                'index': int(nmem[len('/dev/nmem')]),
                'dev': nmem.removeprefix('/dev/'),
                'dev_path': nmem,
                'specrev': int(specrev.strip()),
                'state_flags': state_flags(nmem),
            }
            entry.update(health_info(output))
            entry.update(vendor_info(output))
            entry.update(get_running_firmware_vers_and_detect_old_bios(output))
            results.append(NvdimmInfo(**entry))

    except Exception:
        logger.error("Unhandled exception obtaining nvdimm info", exc_info=True)

    return results
