"""Unit tests for cpu_info_impl() topology parsing.

Mocks /proc/cpuinfo, os.sysconf, and the per-cpuN sysfs reads so we can
exercise unusual topologies (4-way SMT, mixed separators, multi-package /
multi-die, missing files) without real hardware.
"""

import contextlib
from unittest.mock import patch

from middlewared.utils.cpu import cpu_info_impl


class _FakeDirEntry:
    """Minimal stand-in for a real ``DirEntry`` covering what cpu_info_impl
    actually reaches for: ``.name``, ``.path``, ``.is_dir()``."""

    def __init__(self, name: str):
        self.name = name
        self.path = f"/sys/devices/system/cpu/{name}"

    def is_dir(self) -> bool:
        return True


@contextlib.contextmanager
def mock_topology(
    topology: dict[int, dict[str, str | None]],
    *,
    cpu_count: int | None = None,
    cpu_model: str | None = "Test CPU",
    vendor: str | None = "TestVendor",
    flags: tuple[str, ...] = (),
    extra_dir_names: tuple[str, ...] = (),
):
    """Simulate ``/sys/devices/system/cpu/`` with the supplied topology dict.

    ``topology`` maps logical-CPU id -> { 'core_cpus_list': str|None,
    'physical_package_id': str|None, 'die_id': str|None, 'core_id': str|None }.
    A value of ``None`` simulates a missing file.

    ``extra_dir_names`` injects extra subdirectory names (e.g. 'cpufreq')
    so we can verify the parser skips them.
    """
    if cpu_count is None:
        cpu_count = len(topology)

    entries = [_FakeDirEntry(f"cpu{cid}") for cid in sorted(topology.keys())]
    entries.extend(_FakeDirEntry(name) for name in extra_dir_names)

    @contextlib.contextmanager
    def fake_scandir(path):
        assert path == "/sys/devices/system/cpu/", path
        yield iter(entries)

    def fake_read_str(path):
        for cid, fields in topology.items():
            prefix = f"/sys/devices/system/cpu/cpu{cid}/topology/"
            if path.startswith(prefix):
                return fields.get(path[len(prefix) :])
        return None

    def fake_read_int(path):
        s = fake_read_str(path)
        if s is None:
            return None
        try:
            return int(s)
        except ValueError:
            return None

    # Patch the bindings as info.py sees them: ``os`` is imported as
    # ``import os`` (so ``info.os.sysconf`` reaches the same callable),
    # while ``_read_str`` / ``_read_int`` / ``_read_proc_cpuinfo`` are
    # bound directly into info.py via ``from`` imports.
    with (
        patch(
            "middlewared.utils.cpu.info.os.sysconf",
            return_value=cpu_count,
        ),
        patch(
            "middlewared.utils.cpu.info._read_proc_cpuinfo",
            return_value=(cpu_model, vendor, flags),
        ),
        patch(
            "middlewared.utils.cpu.info.os.scandir",
            side_effect=fake_scandir,
        ),
        patch(
            "middlewared.utils.cpu.info._read_str",
            side_effect=fake_read_str,
        ),
        patch(
            "middlewared.utils.cpu.info._read_int",
            side_effect=fake_read_int,
        ),
    ):
        yield


def test_intel_grouped_smt_4c8t():
    """Classic Intel: cpu0+cpu4 share core_id=0, cpu1+cpu5 share core_id=1, ..."""
    topology = {}
    for primary in range(4):
        sibling = primary + 4
        for cid in (primary, sibling):
            topology[cid] = {
                "core_cpus_list": f"{primary},{sibling}",
                "physical_package_id": "0",
                "die_id": "0",
                "core_id": str(primary),
            }
    with mock_topology(topology, cpu_count=8):
        info = cpu_info_impl()

    assert info["core_count"] == 8
    assert info["physical_core_count"] == 4
    # Primary cpu0..cpu3 map to phys 0..3; siblings cpu4..cpu7 to the same.
    assert info["logical_to_phys"] == {0: 0, 4: 0, 1: 1, 5: 1, 2: 2, 6: 2, 3: 3, 7: 3}
    assert info["phys_to_package"] == {0: 0, 1: 0, 2: 0, 3: 0}
    assert info["phys_to_die"] == {0: 0, 1: 0, 2: 0, 3: 0}
    assert info["phys_to_core_id"] == {0: 0, 1: 1, 2: 2, 3: 3}


def test_amd_consecutive_smt_8c16t():
    """5825U-shape: cpuN+cpu(N+1) share core_id=N/2."""
    topology = {}
    for phys in range(8):
        primary = 2 * phys
        sibling = primary + 1
        for cid in (primary, sibling):
            topology[cid] = {
                "core_cpus_list": f"{primary}-{sibling}",
                "physical_package_id": "0",
                "die_id": "0",
                "core_id": str(phys),
            }
    with mock_topology(topology, cpu_count=16):
        info = cpu_info_impl()

    assert info["physical_core_count"] == 8
    # cpu0+cpu1 -> phys 0, cpu2+cpu3 -> phys 1, ...
    expected_l2p = {2 * p: p for p in range(8)} | {2 * p + 1: p for p in range(8)}
    assert info["logical_to_phys"] == expected_l2p


def test_4way_smt_single_core():
    """POWER-style: 1 physical core, 4 logical CPUs, range '0-3'."""
    topology = {
        cid: {
            "core_cpus_list": "0-3",
            "physical_package_id": "0",
            "die_id": "0",
            "core_id": "0",
        }
        for cid in range(4)
    }
    with mock_topology(topology, cpu_count=4):
        info = cpu_info_impl()

    assert info["physical_core_count"] == 1
    assert info["core_count"] == 4
    assert info["logical_to_phys"] == {0: 0, 1: 0, 2: 0, 3: 0}


def test_mixed_separators_in_cpulist():
    """Hypothetical chip whose core_cpus_list is '0,2-3' (one physical core
    with three online siblings: 0, 2, 3) -- all three siblings preserved."""
    cpus = (0, 2, 3)
    topology = {
        cid: {
            "core_cpus_list": "0,2-3",
            "physical_package_id": "0",
            "die_id": "0",
            "core_id": "0",
        }
        for cid in cpus
    }
    with mock_topology(topology, cpu_count=3):
        info = cpu_info_impl()

    assert info["physical_core_count"] == 1
    assert set(info["logical_to_phys"]) == {0, 2, 3}
    assert all(v == 0 for v in info["logical_to_phys"].values())


def test_multi_package_multi_die():
    """Two packages, each with two dies (CCDs), each die holds 2 phys cores
    with 2 logical CPUs (16 logical total)."""
    topology = {}
    cid = 0
    expected_phys_to_pkg = {}
    expected_phys_to_die = {}
    expected_phys_to_core_id = {}
    phys = 0
    for pkg in (0, 1):
        for die in (0, 1):
            for core in (0, 1):
                primary = cid
                sibling = cid + 1
                # Two logical CPUs per phys core.
                for c in (primary, sibling):
                    topology[c] = {
                        "core_cpus_list": f"{primary},{sibling}",
                        "physical_package_id": str(pkg),
                        "die_id": str(die),
                        "core_id": str(core),
                    }
                expected_phys_to_pkg[phys] = pkg
                expected_phys_to_die[phys] = die
                expected_phys_to_core_id[phys] = core
                phys += 1
                cid += 2

    with mock_topology(topology, cpu_count=cid):
        info = cpu_info_impl()

    assert info["physical_core_count"] == 8
    assert info["phys_to_package"] == expected_phys_to_pkg
    assert info["phys_to_die"] == expected_phys_to_die
    assert info["phys_to_core_id"] == expected_phys_to_core_id


def test_smt_disabled_single_thread_per_core():
    """SMT off: core_cpus_list contains just the primary's id, 1 logical
    per phys core."""
    topology = {
        cid: {
            "core_cpus_list": str(cid),
            "physical_package_id": "0",
            "die_id": "0",
            "core_id": str(cid),
        }
        for cid in range(4)
    }
    with mock_topology(topology, cpu_count=4):
        info = cpu_info_impl()

    assert info["physical_core_count"] == 4
    assert info["logical_to_phys"] == {0: 0, 1: 1, 2: 2, 3: 3}


def test_missing_topology_files_skipped():
    """If core_cpus_list is missing for a cpuN, that cpu is silently
    skipped — no crash, no partial entry."""
    topology = {
        0: {
            "core_cpus_list": "0",
            "physical_package_id": "0",
            "die_id": "0",
            "core_id": "0",
        },
        1: {
            "core_cpus_list": None,  # file missing
            "physical_package_id": None,
            "die_id": None,
            "core_id": None,
        },
    }
    with mock_topology(topology, cpu_count=2):
        info = cpu_info_impl()

    assert info["physical_core_count"] == 1
    assert info["logical_to_phys"] == {0: 0}


def test_non_numeric_subdirs_skipped():
    """Subdirs like 'cpufreq', 'cpuidle' must not be interpreted as logical
    CPUs even though their names start with 'cpu'."""
    topology = {
        0: {
            "core_cpus_list": "0",
            "physical_package_id": "0",
            "die_id": "0",
            "core_id": "0",
        },
    }
    with mock_topology(
        topology,
        cpu_count=1,
        extra_dir_names=("cpufreq", "cpuidle"),
    ):
        info = cpu_info_impl()

    assert info["physical_core_count"] == 1


def test_negative_topology_ids_normalized_to_zero():
    """Some kernels expose physical_package_id=-1 or die_id=-1 on systems
    without that topology level. Treat them as 0 so attribution still
    works (single-package/single-die fallback)."""
    topology = {
        0: {
            "core_cpus_list": "0",
            "physical_package_id": "-1",
            "die_id": "-1",
            "core_id": "0",
        },
    }
    with mock_topology(topology, cpu_count=1):
        info = cpu_info_impl()

    assert info["phys_to_package"] == {0: 0}
    assert info["phys_to_die"] == {0: 0}


def test_proc_cpuinfo_extraction():
    """The (model_name, vendor_id, flags) tuple from /proc/cpuinfo is
    surfaced verbatim."""
    topology = {
        0: {
            "core_cpus_list": "0",
            "physical_package_id": "0",
            "die_id": "0",
            "core_id": "0",
        },
    }
    with mock_topology(
        topology,
        cpu_count=1,
        cpu_model="Some CPU Model",
        vendor="AuthenticAMD",
        flags=("sse", "sse2", "avx"),
    ):
        info = cpu_info_impl()

    assert info["cpu_model"] == "Some CPU Model"
    assert info["vendor_id"] == "AuthenticAMD"
    assert info["cpu_flags"] == ("sse", "sse2", "avx")
