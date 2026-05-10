"""Unit tests for ``_resolve_chip_package``."""

from unittest.mock import patch

from middlewared.utils.cpu.hwmon import _resolve_chip_package


def test_resolve_coretemp_uses_package_label():
    """coretemp's ``Package id N`` label drives package resolution."""
    labels = {
        "Package id 3": "/sys/class/hwmon/hwmon0/temp1_input",
        "Core 0": "/sys/class/hwmon/hwmon0/temp2_input",
        "Core 1": "/sys/class/hwmon/hwmon0/temp3_input",
    }
    pkg = _resolve_chip_package(
        "/sys/class/hwmon/hwmon0",
        "coretemp",
        labels,
        fallback_index=99,
    )
    assert pkg == 3


def test_resolve_coretemp_falls_back_to_platform_device_name():
    """If a coretemp chip somehow lacks a 'Package id N' label, fall
    back to the platform-device basename (``coretemp.M`` -> ``M``)."""
    labels = {
        "Core 0": "/sys/class/hwmon/hwmon0/temp1_input",
        "Core 1": "/sys/class/hwmon/hwmon0/temp2_input",
    }
    with patch(
        "middlewared.utils.cpu.hwmon.os.path.realpath",
        return_value="/sys/devices/platform/coretemp.2",
    ):
        pkg = _resolve_chip_package(
            "/sys/class/hwmon/hwmon0",
            "coretemp",
            labels,
            fallback_index=99,
        )
    assert pkg == 2


def test_resolve_coretemp_final_fallback_is_alphabetical_index():
    """No 'Package id' label and an unrecognised device path -> the
    alphabetical fallback_index is the last resort."""
    labels = {"Core 0": "/sys/class/hwmon/hwmon0/temp1_input"}
    with patch(
        "middlewared.utils.cpu.hwmon.os.path.realpath",
        return_value="/sys/devices/platform/something_unrelated",
    ):
        pkg = _resolve_chip_package(
            "/sys/class/hwmon/hwmon0",
            "coretemp",
            labels,
            fallback_index=7,
        )
    assert pkg == 7


def test_resolve_k10temp_uses_numa_node():
    """k10temp's PCI device exposes ``numa_node``; we cross-reference
    ``_numa_to_pkg()`` to recover the package id."""
    with (
        patch(
            "middlewared.utils.cpu.hwmon._read_int",
            return_value=1,
        ),
        patch(
            "middlewared.utils.cpu.hwmon._numa_to_pkg",
            return_value={1: 1},
        ),
    ):
        pkg = _resolve_chip_package(
            "/sys/class/hwmon/hwmon1",
            "k10temp",
            {},
            fallback_index=99,
        )
    assert pkg == 1


def test_resolve_k10temp_falls_back_when_numa_missing():
    """numa_node == -1 (BIOS quirk, single-socket boxes) falls back to
    the alphabetical index."""
    with (
        patch(
            "middlewared.utils.cpu.hwmon._read_int",
            return_value=-1,
        ),
        patch(
            "middlewared.utils.cpu.hwmon._numa_to_pkg",
            return_value={},
        ),
    ):
        pkg = _resolve_chip_package(
            "/sys/class/hwmon/hwmon1",
            "k10temp",
            {},
            fallback_index=0,
        )
    assert pkg == 0


def test_resolve_k10temp_falls_back_when_numa_unmapped():
    """numa_node is set but not in _numa_to_pkg (corrupt/incomplete
    NUMA topology) -> alphabetical fallback."""
    with (
        patch(
            "middlewared.utils.cpu.hwmon._read_int",
            return_value=4,
        ),
        patch(
            "middlewared.utils.cpu.hwmon._numa_to_pkg",
            return_value={0: 0, 1: 1},
        ),
    ):
        pkg = _resolve_chip_package(
            "/sys/class/hwmon/hwmon1",
            "k10temp",
            {},
            fallback_index=1,
        )
    assert pkg == 1


def test_resolve_via_cputemp_is_package_zero():
    pkg = _resolve_chip_package(
        "/sys/class/hwmon/hwmon0",
        "via_cputemp",
        {},
        fallback_index=99,
    )
    assert pkg == 0


def test_resolve_cpu_thermal_is_package_zero():
    pkg = _resolve_chip_package(
        "/sys/class/hwmon/hwmon0",
        "cpu_thermal",
        {},
        fallback_index=99,
    )
    assert pkg == 0
