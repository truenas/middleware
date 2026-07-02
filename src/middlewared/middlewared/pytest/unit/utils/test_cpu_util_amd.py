# -*- coding=utf-8 -*-
from middlewared.utils.cpu import _amd_assignments


def test_amd_tccd_wins_over_package_fallback():
    """Single CCD: Tccd1 is assigned to every core on die0; Tctl/Tdie only
    fill cores a Tccd didn't cover (none here)."""
    out = _amd_assignments(
        {'Tctl': 48.625, 'Tdie': 48.625, 'Tccd1': 54.750},
        chip_pkg=0,
        cpu_model='AMD Ryzen 5 3600 6-Core Processor',
        pkg_to_phys={0: [0, 1, 2, 3, 4, 5]},
        pkg_die_to_phys={(0, 0): [0, 1, 2, 3, 4, 5]},
    )
    assert out == {i: 54.750 for i in range(6)}


def test_amd_prefer_tdie_ignores_tccd():
    """AMD_PREFER_TDIE model with Tdie present: Tdie everywhere, Tccd skipped."""
    out = _amd_assignments(
        {'Tctl': 67.0, 'Tdie': 40.0, 'Tccd1': 65.5},
        chip_pkg=0,
        cpu_model='AMD Ryzen Threadripper 1950X 16-Core Processor',
        pkg_to_phys={0: list(range(16))},
        pkg_die_to_phys={(0, 0): list(range(16))},
    )
    assert out == {i: 40.0 for i in range(16)}


def test_amd_temp1_fallback():
    """Legacy k8temp / APU with only temp1: broadcast across the package."""
    out = _amd_assignments(
        {'temp1': 48.23},
        chip_pkg=0,
        cpu_model='AMD Opteron APU  1-Core Processor',
        pkg_to_phys={0: [0]},
        pkg_die_to_phys={},
    )
    assert out == {0: 48.23}


def test_amd_multi_ccd_split_by_die():
    out = _amd_assignments(
        {'Tctl': 50.0, 'Tdie': 48.0, 'Tccd1': 52.0, 'Tccd2': 54.0},
        chip_pkg=0,
        cpu_model='AMD Ryzen 9 3950X 16-Core Processor',
        pkg_to_phys={0: list(range(16))},
        pkg_die_to_phys={(0, 0): list(range(8)), (0, 1): list(range(8, 16))},
    )
    assert out == {i: 52.0 for i in range(8)} | {i: 54.0 for i in range(8, 16)}


def test_amd_asymmetric_ccd():
    out = _amd_assignments(
        {'Tctl': 50.0, 'Tccd1': 52.0, 'Tccd2': 54.0},
        chip_pkg=0,
        cpu_model='AMD Ryzen 9 5900X 12-Core Processor',
        pkg_to_phys={0: list(range(12))},
        pkg_die_to_phys={(0, 0): [0, 1, 2, 3], (0, 1): list(range(4, 12))},
    )
    assert out == {0: 52.0, 1: 52.0, 2: 52.0, 3: 52.0} | {i: 54.0 for i in range(4, 12)}


def test_amd_partial_ccd_coverage_uses_fallback():
    """Only Tccd1 reported: die0 gets Tccd1, die1 falls back to Tctl."""
    out = _amd_assignments(
        {'Tctl': 50.0, 'Tccd1': 60.0},
        chip_pkg=0,
        cpu_model='AMD Ryzen 9 3950X 16-Core Processor',
        pkg_to_phys={0: list(range(16))},
        pkg_die_to_phys={(0, 0): list(range(8)), (0, 1): list(range(8, 16))},
    )
    assert out == {i: 60.0 for i in range(8)} | {i: 50.0 for i in range(8, 16)}


def test_amd_zero_reading_preserved():
    """0.0 is a valid reading (isinstance check, not truthiness)."""
    out = _amd_assignments(
        {'Tctl': 50.0, 'Tccd1': 0.0},
        chip_pkg=0,
        cpu_model='AMD Ryzen 5 5600 6-Core Processor',
        pkg_to_phys={0: [0, 1]},
        pkg_die_to_phys={(0, 0): [0, 1]},
    )
    assert out == {0: 0.0, 1: 0.0}


def test_amd_multi_socket_no_cross_package_bleed():
    """chip_pkg scopes a chip's readings to its own package's cores."""
    out = _amd_assignments(
        {'Tctl': 70.0},
        chip_pkg=1,
        cpu_model='AMD EPYC 7302 16-Core Processor',
        pkg_to_phys={0: [0, 1, 2, 3], 1: [4, 5, 6, 7]},
        pkg_die_to_phys={(0, 0): [0, 1, 2, 3], (1, 0): [4, 5, 6, 7]},
    )
    assert out == {4: 70.0, 5: 70.0, 6: 70.0, 7: 70.0}
