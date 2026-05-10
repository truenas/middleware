"""Unit tests for the topology-driven CPU temperature pipeline.

The production code reads /sys/class/hwmon directly. We mock four extension
points to cover every branch without touching real sysfs:

  - ``cpu_info``                : the topology TypedDict
  - ``_phys_indexes``           : derived index dict (pre-computed in prod)
  - ``_discover_cpu_chips``     : the tuple of _Chip dataclasses
  - ``_read_chip_temps``        : per-chip label -> celsius dict

Helpers ``make_cinfo`` / ``make_chip`` / ``patched_env`` keep fixtures compact.
"""

import collections
from contextlib import contextmanager
from unittest.mock import patch

from middlewared.utils.cpu import get_cpu_temperatures
from middlewared.utils.cpu.hwmon import _Chip
from middlewared.utils.cpu.temperatures import _PhysIndexes


def make_cinfo(
    *,
    cpu_model="Test CPU",
    logical_to_phys,
    phys_to_package=None,
    phys_to_die=None,
    phys_to_core_id=None,
    core_count=None,
    physical_core_count=None,
):
    """Build a CpuInfo-shaped dict for tests with sensible defaults."""
    if physical_core_count is None:
        physical_core_count = len(set(logical_to_phys.values()))
    if core_count is None:
        core_count = len(logical_to_phys)
    if phys_to_package is None:
        phys_to_package = {p: 0 for p in range(physical_core_count)}
    if phys_to_die is None:
        phys_to_die = {p: 0 for p in range(physical_core_count)}
    if phys_to_core_id is None:
        phys_to_core_id = {p: p for p in range(physical_core_count)}
    return {
        "cpu_model": cpu_model,
        "vendor_id": "TestVendor",
        "cpu_flags": (),
        "core_count": core_count,
        "physical_core_count": physical_core_count,
        "logical_to_phys": logical_to_phys,
        "phys_to_package": phys_to_package,
        "phys_to_die": phys_to_die,
        "phys_to_core_id": phys_to_core_id,
    }


def make_chip(name, package_id, temps, hwmon_id=0):
    """Build a _Chip whose label_to_input keys are the labels we want to
    expose. The path values are placeholders since _read_chip_temps is
    mocked away."""
    return _Chip(
        hwmon_path=f"/fake/hwmon{hwmon_id}",
        name=name,
        package_id=package_id,
        label_to_input=tuple((label, "") for label in temps),
    )


def _build_indexes(cinfo):
    pkg_to_phys = collections.defaultdict(list)
    pkg_die_to_phys = collections.defaultdict(list)
    pkg_core_to_phys = collections.defaultdict(dict)
    for phys, pkg in cinfo["phys_to_package"].items():
        pkg_to_phys[pkg].append(phys)
        pkg_die_to_phys[(pkg, cinfo["phys_to_die"][phys])].append(phys)
        pkg_core_to_phys[pkg][cinfo["phys_to_core_id"][phys]] = phys
    return _PhysIndexes(
        pkg_to_phys=dict(pkg_to_phys),
        pkg_die_to_phys=dict(pkg_die_to_phys),
        pkg_core_to_phys={k: dict(v) for k, v in pkg_core_to_phys.items()},
    )


@contextmanager
def patched_env(cinfo, chips_with_temps):
    """chips_with_temps: list of (_Chip, dict[label, float])."""
    chips = tuple(c for c, _ in chips_with_temps)
    temp_map = {id(c): t for c, t in chips_with_temps}
    indexes = _build_indexes(cinfo)
    # Patch the bindings as imported by temperatures.py — the only consumer
    # of these symbols on the hot path. Patching here covers every code path
    # exercised by get_cpu_temperatures() without affecting the rest of the
    # cpu sub-package.
    with (
        patch(
            "middlewared.utils.cpu.temperatures.cpu_info",
            return_value=cinfo,
        ),
        patch(
            "middlewared.utils.cpu.temperatures._phys_indexes",
            return_value=indexes,
        ),
        patch(
            "middlewared.utils.cpu.temperatures._discover_cpu_chips",
            return_value=chips,
        ),
        patch(
            "middlewared.utils.cpu.temperatures._read_chip_temps",
            side_effect=lambda c: temp_map.get(id(c), {}),
        ),
    ):
        yield


def test_intel_single_package_grouped_smt():
    """i5-8250U-style: 4 physical / 8 logical, cpu0..cpu3 are primaries,
    cpu4..cpu7 are HT siblings (Intel "grouped" enumeration)."""
    cinfo = make_cinfo(
        cpu_model="Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz",
        logical_to_phys={
            0: 0,
            4: 0,
            1: 1,
            5: 1,
            2: 2,
            6: 2,
            3: 3,
            7: 3,
        },
        phys_to_core_id={0: 0, 1: 1, 2: 2, 3: 3},
    )
    chip = make_chip(
        "coretemp",
        0,
        {
            "Package id 0": 45.0,
            "Core 0": 48.0,
            "Core 1": 49.0,
            "Core 2": 47.0,
            "Core 3": 50.0,
        },
    )
    with patched_env(
        cinfo,
        [
            (
                chip,
                {
                    "Package id 0": 45.0,
                    "Core 0": 48.0,
                    "Core 1": 49.0,
                    "Core 2": 47.0,
                    "Core 3": 50.0,
                },
            )
        ],
    ):
        result = get_cpu_temperatures()

    expected = {
        "cpu0": 48.0,
        "cpu4": 48.0,
        "cpu1": 49.0,
        "cpu5": 49.0,
        "cpu2": 47.0,
        "cpu6": 47.0,
        "cpu3": 50.0,
        "cpu7": 50.0,
        "cpu": (48.0 + 49.0 + 47.0 + 50.0) / 4,
    }
    assert result == expected


def test_intel_single_package_consecutive_smt():
    """Same chip, but firmware enumerates SMT siblings consecutively
    (cpu0+cpu1 share a physical core)."""
    cinfo = make_cinfo(
        cpu_model="Intel(R) Synthetic 4C/8T consecutive",
        logical_to_phys={
            0: 0,
            1: 0,
            2: 1,
            3: 1,
            4: 2,
            5: 2,
            6: 3,
            7: 3,
        },
        phys_to_core_id={0: 0, 1: 1, 2: 2, 3: 3},
    )
    chip = make_chip(
        "coretemp",
        0,
        {
            "Package id 0": 45.0,
            "Core 0": 48.0,
            "Core 1": 49.0,
            "Core 2": 47.0,
            "Core 3": 50.0,
        },
    )
    with patched_env(
        cinfo,
        [
            (
                chip,
                {
                    "Package id 0": 45.0,
                    "Core 0": 48.0,
                    "Core 1": 49.0,
                    "Core 2": 47.0,
                    "Core 3": 50.0,
                },
            )
        ],
    ):
        result = get_cpu_temperatures()

    expected = {
        "cpu0": 48.0,
        "cpu1": 48.0,
        "cpu2": 49.0,
        "cpu3": 49.0,
        "cpu4": 47.0,
        "cpu5": 47.0,
        "cpu6": 50.0,
        "cpu7": 50.0,
        "cpu": (48.0 + 49.0 + 47.0 + 50.0) / 4,
    }
    assert result == expected


def test_intel_dual_socket_uses_package_label():
    """Two coretemp chips. Package mapping must come from the chip's own
    'Package id N' label, not from alphabetical chip name ordering."""
    cinfo = make_cinfo(
        cpu_model="Intel(R) Xeon(R) E5-2690 v4",
        logical_to_phys={0: 0, 1: 1, 2: 2, 3: 3},  # no SMT for simplicity
        phys_to_package={0: 0, 1: 0, 2: 1, 3: 1},
        phys_to_die={0: 0, 1: 0, 2: 0, 3: 0},
        phys_to_core_id={0: 0, 1: 1, 2: 0, 3: 1},
    )
    chip0 = make_chip(
        "coretemp",
        0,
        {
            "Package id 0": 36.0,
            "Core 0": 48.0,
            "Core 1": 49.0,
        },
        hwmon_id=0,
    )
    chip1 = make_chip(
        "coretemp",
        1,
        {
            "Package id 1": 45.0,
            "Core 0": 55.0,
            "Core 1": 54.0,
        },
        hwmon_id=1,
    )
    with patched_env(
        cinfo,
        [
            (chip0, {"Package id 0": 36.0, "Core 0": 48.0, "Core 1": 49.0}),
            (chip1, {"Package id 1": 45.0, "Core 0": 55.0, "Core 1": 54.0}),
        ],
    ):
        result = get_cpu_temperatures()

    expected = {
        "cpu0": 48.0,
        "cpu1": 49.0,
        "cpu2": 55.0,
        "cpu3": 54.0,
        "cpu": (48.0 + 49.0 + 55.0 + 54.0) / 4,
    }
    assert result == expected


def test_amd_ryzen_5_3600_single_ccd():
    """Tccd1 must apply to all 6 physical cores; HT siblings get the same."""
    cinfo = make_cinfo(
        cpu_model="AMD Ryzen 5 3600 6-Core Processor",
        logical_to_phys={i: i for i in range(6)} | {i + 6: i for i in range(6)},
    )
    chip = make_chip("k10temp", 0, {"Tctl": 48.625, "Tdie": 48.625, "Tccd1": 54.750})
    with patched_env(
        cinfo,
        [
            (
                chip,
                {
                    "Tctl": 48.625,
                    "Tdie": 48.625,
                    "Tccd1": 54.750,
                },
            )
        ],
    ):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 54.750 for i in range(12)}
    expected["cpu"] = 54.750
    assert result == expected


def test_amd_prefer_tdie_overrides_tccd():
    """AMD_PREFER_TDIE chip with Tdie present: Tdie must win for every core
    in the package. Tccd1 must be ignored even though it's present."""
    cinfo = make_cinfo(
        cpu_model="AMD Ryzen Threadripper 1950X 16-Core Processor",
        logical_to_phys={i: i for i in range(16)} | {i + 16: i for i in range(16)},
    )
    chip = make_chip("k10temp", 0, {"Tctl": 67.0, "Tdie": 40.0, "Tccd1": 65.5})
    with patched_env(
        cinfo,
        [
            (
                chip,
                {
                    "Tctl": 67.0,
                    "Tdie": 40.0,
                    "Tccd1": 65.5,
                },
            )
        ],
    ):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 40.0 for i in range(32)}
    expected["cpu"] = 40.0
    assert result == expected


def test_amd_prefer_tdie_without_tdie_cascades_to_tctl():
    """When the chip is in AMD_PREFER_TDIE but the kernel doesn't expose
    Tdie, fall through to the cascade. Tctl should be used."""
    cinfo = make_cinfo(
        cpu_model="AMD Ryzen Threadripper 1950X 16-Core Processor",
        logical_to_phys={i: i for i in range(16)} | {i + 16: i for i in range(16)},
    )
    chip = make_chip("k10temp", 0, {"Tctl": 67.0})
    with patched_env(cinfo, [(chip, {"Tctl": 67.0})]):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 67.0 for i in range(32)}
    expected["cpu"] = 67.0
    assert result == expected


def test_amd_multi_ccd_fully_populated():
    """Ryzen 9 3950X: 16 phys cores split 8/8 across two CCDs. Per-die
    attribution via die_id, not even-split modulo."""
    # First 8 phys cores on die 0, next 8 on die 1.
    phys_to_die = {p: (0 if p < 8 else 1) for p in range(16)}
    cinfo = make_cinfo(
        cpu_model="AMD Ryzen 9 3950X 16-Core Processor",
        logical_to_phys={i: i for i in range(16)} | {i + 16: i for i in range(16)},
        phys_to_die=phys_to_die,
    )
    chip = make_chip(
        "k10temp",
        0,
        {
            "Tctl": 50.0,
            "Tdie": 48.0,
            "Tccd1": 52.0,
            "Tccd2": 54.0,
        },
    )
    with patched_env(
        cinfo,
        [
            (
                chip,
                {
                    "Tctl": 50.0,
                    "Tdie": 48.0,
                    "Tccd1": 52.0,
                    "Tccd2": 54.0,
                },
            )
        ],
    ):
        result = get_cpu_temperatures()

    expected = {}
    for i in range(8):
        expected[f"cpu{i}"] = 52.0
        expected[f"cpu{i + 16}"] = 52.0
    for i in range(8, 16):
        expected[f"cpu{i}"] = 54.0
        expected[f"cpu{i + 16}"] = 54.0
    # Physical-core mean: 8 cores at 52, 8 cores at 54.
    expected["cpu"] = (52.0 * 8 + 54.0 * 8) / 16
    assert result == expected


def test_amd_asymmetric_ccds():
    """A 12-core chip with one fully-fused-off-half CCD: die 0 has 4 phys
    cores, die 1 has 8. Per-die assignment handles this natively without
    requiring a `core_count % len(ccds) == 0` divisibility check."""
    phys_to_die = {p: (0 if p < 4 else 1) for p in range(12)}
    cinfo = make_cinfo(
        cpu_model="AMD synthetic 12C/24T asymmetric CCD",
        logical_to_phys={i: i for i in range(12)} | {i + 12: i for i in range(12)},
        phys_to_die=phys_to_die,
    )
    chip = make_chip("k10temp", 0, {"Tctl": 50.0, "Tccd1": 52.0, "Tccd2": 54.0})
    with patched_env(
        cinfo,
        [
            (
                chip,
                {
                    "Tctl": 50.0,
                    "Tccd1": 52.0,
                    "Tccd2": 54.0,
                },
            )
        ],
    ):
        result = get_cpu_temperatures()

    expected = {}
    for i in range(4):
        expected[f"cpu{i}"] = 52.0
        expected[f"cpu{i + 12}"] = 52.0
    for i in range(4, 12):
        expected[f"cpu{i}"] = 54.0
        expected[f"cpu{i + 12}"] = 54.0
    expected["cpu"] = (52.0 * 4 + 54.0 * 8) / 12
    assert result == expected


def test_amd_partial_ccd_coverage_falls_back():
    """Multi-CCD chip where only Tccd1 is reported. Cores on die 1 must
    fall back to the package-wide reading (Tctl), not be dropped."""
    phys_to_die = {p: (0 if p < 8 else 1) for p in range(16)}
    cinfo = make_cinfo(
        cpu_model="AMD synthetic 16C/16T partial CCD coverage",
        logical_to_phys={i: i for i in range(16)},
        phys_to_die=phys_to_die,
    )
    chip = make_chip("k10temp", 0, {"Tctl": 50.0, "Tccd1": 60.0})
    with patched_env(cinfo, [(chip, {"Tctl": 50.0, "Tccd1": 60.0})]):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 60.0 for i in range(8)}  # die 0 -> Tccd1
    expected.update({f"cpu{i}": 50.0 for i in range(8, 16)})  # die 1 -> Tctl
    expected["cpu"] = (60.0 * 8 + 50.0 * 8) / 16
    assert result == expected


def test_amd_ryzen_5825u_consecutive_smt_tctl_only():
    """k10temp exposes only Tctl. Kernel pairs cpuN/cpuN+1. All 16 logical
    CPUs must be populated and the aggregate must equal Tctl."""
    cinfo = make_cinfo(
        cpu_model="AMD Ryzen 7 5825U with Radeon Graphics",
        logical_to_phys={2 * p: p for p in range(8)} | {2 * p + 1: p for p in range(8)},
    )
    chip = make_chip("k10temp", 0, {"Tctl": 51.1})
    with patched_env(cinfo, [(chip, {"Tctl": 51.1})]):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 51.1 for i in range(16)}
    expected["cpu"] = 51.1
    assert result == expected


def test_amd_multi_socket_distinct_packages():
    """Two k10temp chips with distinct package_ids; neither overwrites
    the other."""
    cinfo = make_cinfo(
        cpu_model="AMD EPYC dual-socket synthetic",
        logical_to_phys={i: i for i in range(8)},
        phys_to_package={0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 1},
    )
    chip0 = make_chip("k10temp", 0, {"Tctl": 60.0}, hwmon_id=0)
    chip1 = make_chip("k10temp", 1, {"Tctl": 70.0}, hwmon_id=1)
    with patched_env(
        cinfo,
        [
            (chip0, {"Tctl": 60.0}),
            (chip1, {"Tctl": 70.0}),
        ],
    ):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 60.0 for i in range(4)}
    expected.update({f"cpu{i}": 70.0 for i in range(4, 8)})
    expected["cpu"] = (60.0 * 4 + 70.0 * 4) / 8
    assert result == expected


def test_amd_multi_socket_fallback_indexes():
    """Chips reported in alphabetical order with monotonically-increasing
    package_id (the fallback _resolve_chip_package() picks when numa_node
    lookup fails). Verifies the fallback path produces correct attribution."""
    cinfo = make_cinfo(
        cpu_model="AMD EPYC dual-socket synthetic",
        logical_to_phys={i: i for i in range(8)},
        phys_to_package={0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 1},
    )
    # Caller would have already used the alphabetical fallback to assign
    # package_id=0 and package_id=1. We're testing that downstream is OK
    # with whatever package_id resolution returned.
    chip_a = make_chip("k10temp", 0, {"Tctl": 60.0}, hwmon_id=0)
    chip_b = make_chip("k10temp", 1, {"Tctl": 70.0}, hwmon_id=1)
    with patched_env(
        cinfo,
        [
            (chip_a, {"Tctl": 60.0}),
            (chip_b, {"Tctl": 70.0}),
        ],
    ):
        result = get_cpu_temperatures()

    assert result["cpu0"] == 60.0
    assert result["cpu7"] == 70.0
    assert result["cpu"] == (60.0 * 4 + 70.0 * 4) / 8


def test_amd_k8temp_legacy_temp1():
    """k8temp exposes only temp1 (no Tctl/Tdie/Tccd labels). It should
    broadcast across every phys core in its package via the package
    fallback."""
    cinfo = make_cinfo(
        cpu_model="AMD Opteron APU 1-Core Processor",
        logical_to_phys={0: 0},
    )
    chip = make_chip("k8temp", 0, {"temp1": 48.23})
    with patched_env(cinfo, [(chip, {"temp1": 48.23})]):
        result = get_cpu_temperatures()

    assert result == {"cpu0": 48.23, "cpu": 48.23}


def test_4way_smt_all_siblings_populated():
    """A POWER-style chip with core_cpus_list = '0-3' (4-way SMT); every
    sibling gets the physical core's temperature."""
    cinfo = make_cinfo(
        cpu_model="IBM POWER9 (synthetic)",
        # 1 physical core, 4 logical (cpu0..cpu3 all on phys 0).
        logical_to_phys={0: 0, 1: 0, 2: 0, 3: 0},
    )
    # Use a single-temp chip (cpu_thermal-style) so the package fallback
    # broadcasts to every phys core in the package.
    chip = make_chip("cpu_thermal", 0, {"temp1": 70.0})
    with patched_env(cinfo, [(chip, {"temp1": 70.0})]):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 70.0 for i in range(4)}
    expected["cpu"] = 70.0
    assert result == expected


def test_partial_smt_only_online_logicals_assigned():
    """An 8-physical-core box with only some HT siblings online. Every
    logical CPU in logical_to_phys gets its phys core's temp; offline
    logicals don't appear (and can't be missed because logical_to_phys is
    the authoritative source)."""
    cinfo = make_cinfo(
        cpu_model="AMD synthetic 8C partial SMT",
        # 4 paired physical cores (cpu0+cpu1, cpu2+cpu3, cpu4+cpu5, cpu6+cpu7)
        # plus 4 unpaired cores (cpu8, cpu10, cpu12, cpu14 — siblings offline).
        logical_to_phys={
            0: 0,
            1: 0,
            2: 1,
            3: 1,
            4: 2,
            5: 2,
            6: 3,
            7: 3,
            8: 4,
            10: 5,
            12: 6,
            14: 7,
        },
        core_count=12,  # 12 online logical CPUs
        physical_core_count=8,
    )
    chip = make_chip("k10temp", 0, {"Tctl": 55.0})
    with patched_env(cinfo, [(chip, {"Tctl": 55.0})]):
        result = get_cpu_temperatures()

    expected = {f"cpu{lid}": 55.0 for lid in cinfo["logical_to_phys"]}
    # Aggregate is physical-core mean, immune to asymmetric SMT counts.
    expected["cpu"] = 55.0
    assert result == expected


def test_no_chips_returns_zero_fallback():
    """No CPU thermal chip discovered: the function must still return the
    full fallback dict so netdata's chart dimensions stay populated."""
    cinfo = make_cinfo(
        cpu_model="Unknown CPU",
        logical_to_phys={i: i for i in range(4)},
    )
    with patched_env(cinfo, []):
        result = get_cpu_temperatures()

    expected = {f"cpu{i}": 0.0 for i in range(4)}
    expected["cpu"] = 0.0
    assert result == expected


def _amd_zero_cinfo():
    return make_cinfo(
        cpu_model="AMD Ryzen 7 5825U with Radeon Graphics",
        logical_to_phys={2 * p: p for p in range(2)} | {2 * p + 1: p for p in range(2)},
    )


def test_amd_zero_tccd_preserved():
    cinfo = _amd_zero_cinfo()
    chip = make_chip("k10temp", 0, {"Tctl": 50.0, "Tccd1": 0.0})
    with patched_env(cinfo, [(chip, {"Tctl": 50.0, "Tccd1": 0.0})]):
        result = get_cpu_temperatures()
    expected = {f"cpu{i}": 0.0 for i in range(4)}
    expected["cpu"] = 0.0
    assert result == expected


def test_amd_zero_tdie_preserved_on_prefer_tdie():
    cinfo = make_cinfo(
        cpu_model="AMD Ryzen Threadripper 1950X 16-Core Processor",
        logical_to_phys={i: i for i in range(16)} | {i + 16: i for i in range(16)},
    )
    chip = make_chip("k10temp", 0, {"Tctl": 50.0, "Tdie": 0.0})
    with patched_env(cinfo, [(chip, {"Tctl": 50.0, "Tdie": 0.0})]):
        result = get_cpu_temperatures()
    expected = {f"cpu{i}": 0.0 for i in range(32)}
    expected["cpu"] = 0.0
    assert result == expected


def test_amd_zero_tctl_preserved():
    cinfo = _amd_zero_cinfo()
    chip = make_chip("k10temp", 0, {"Tctl": 0.0})
    with patched_env(cinfo, [(chip, {"Tctl": 0.0})]):
        result = get_cpu_temperatures()
    expected = {f"cpu{i}": 0.0 for i in range(4)}
    expected["cpu"] = 0.0
    assert result == expected


def test_amd_zero_temp1_preserved():
    cinfo = make_cinfo(
        cpu_model="AMD Opteron APU 1-Core Processor",
        logical_to_phys={0: 0},
    )
    chip = make_chip("k8temp", 0, {"temp1": 0.0})
    with patched_env(cinfo, [(chip, {"temp1": 0.0})]):
        result = get_cpu_temperatures()
    assert result == {"cpu0": 0.0, "cpu": 0.0}


def test_tccd_scrambled_insertion_order_does_not_break_assignment():
    """Tccd label parsing must not depend on dict insertion order. Each
    Tccd<N> is matched to die N-1 by name, regardless of how it was
    inserted into the chip dict. Unmatched Tccds (no die with that index)
    are silently ignored."""
    # Synthetic 24C/24T with 12 dies, 2 cores per die.
    phys_to_die = {p: p // 2 for p in range(24)}
    cinfo = make_cinfo(
        cpu_model="AMD synthetic 24C 12-CCD",
        logical_to_phys={i: i for i in range(24)},
        phys_to_die=phys_to_die,
    )
    tccds = {f"Tccd{i}": float(i) for i in range(1, 13)}
    scrambled = {
        "Tctl": 50.0,
        "Tccd10": tccds["Tccd10"],
        "Tccd2": tccds["Tccd2"],
        "Tccd11": tccds["Tccd11"],
        "Tccd1": tccds["Tccd1"],
        "Tccd12": tccds["Tccd12"],
        "Tccd5": tccds["Tccd5"],
        "Tccd3": tccds["Tccd3"],
        "Tccd9": tccds["Tccd9"],
        "Tccd4": tccds["Tccd4"],
        "Tccd7": tccds["Tccd7"],
        "Tccd6": tccds["Tccd6"],
        "Tccd8": tccds["Tccd8"],
    }
    chip = make_chip("k10temp", 0, scrambled)
    with patched_env(cinfo, [(chip, scrambled)]):
        result = get_cpu_temperatures()

    expected = {}
    for ccd in range(1, 13):
        expected[f"cpu{2 * (ccd - 1)}"] = float(ccd)
        expected[f"cpu{2 * (ccd - 1) + 1}"] = float(ccd)
    expected["cpu"] = sum(float(i) * 2 for i in range(1, 13)) / 24
    assert result == expected


def test_unmatched_tccd_is_silently_ignored():
    """A chip reporting Tccd5 on a system whose dies are only 0..3 must not
    raise; the unmatched Tccd is ignored and missing-die cores fall back."""
    phys_to_die = {p: p // 2 for p in range(8)}  # dies 0..3
    cinfo = make_cinfo(
        cpu_model="AMD synthetic 8C 4-CCD",
        logical_to_phys={i: i for i in range(8)},
        phys_to_die=phys_to_die,
    )
    chip = make_chip("k10temp", 0, {"Tctl": 50.0, "Tccd5": 99.0})
    with patched_env(cinfo, [(chip, {"Tctl": 50.0, "Tccd5": 99.0})]):
        result = get_cpu_temperatures()
    expected = {f"cpu{i}": 50.0 for i in range(8)}
    expected["cpu"] = 50.0
    assert result == expected


def test_aggregate_immune_to_asymmetric_smt():
    """The 'cpu' aggregate is the physical-core mean, not the logical-CPU
    mean. On asymmetric SMT this matters: the aggregate must be the mean
    of distinct phys-core temps regardless of how many logical CPUs each
    phys core has online."""
    cinfo = make_cinfo(
        cpu_model="Asymmetric synthetic",
        # phys 0 has 2 online logicals, phys 1 has 1, phys 2 has 1.
        logical_to_phys={0: 0, 1: 0, 2: 1, 3: 2},
        core_count=4,
        physical_core_count=3,
        phys_to_die={0: 0, 1: 0, 2: 0},
        phys_to_core_id={0: 0, 1: 1, 2: 2},
    )
    # Use coretemp so per-core readings reach individual phys cores.
    chip = make_chip(
        "coretemp",
        0,
        {
            "Package id 0": 50.0,
            "Core 0": 30.0,
            "Core 1": 60.0,
            "Core 2": 90.0,
        },
    )
    with patched_env(
        cinfo,
        [
            (
                chip,
                {
                    "Package id 0": 50.0,
                    "Core 0": 30.0,
                    "Core 1": 60.0,
                    "Core 2": 90.0,
                },
            )
        ],
    ):
        result = get_cpu_temperatures()

    # phys 0 -> 30 (mirrored to cpu0+cpu1)
    # phys 1 -> 60 (cpu2)
    # phys 2 -> 90 (cpu3)
    # Aggregate should be (30 + 60 + 90) / 3 = 60, NOT (30+30+60+90)/4 = 52.5.
    assert result == {
        "cpu0": 30.0,
        "cpu1": 30.0,
        "cpu2": 60.0,
        "cpu3": 90.0,
        "cpu": 60.0,
    }
