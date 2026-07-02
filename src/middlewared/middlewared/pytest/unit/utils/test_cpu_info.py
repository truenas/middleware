import pytest

from middlewared.utils.cpu import _numeric, _parse_cpulist, cpu_info_impl


def _write_cpu(root, n, core_cpus_list, package_id=0, die_id=0, core_id=0, write_die=True, write_core=True):
    topo = root / f"cpu{n}" / "topology"
    topo.mkdir(parents=True)
    (topo / "core_cpus_list").write_text(f"{core_cpus_list}\n")
    if package_id is not None:
        (topo / "physical_package_id").write_text(f"{package_id}\n")
    if write_die:
        (topo / "die_id").write_text(f"{die_id}\n")
    if write_core:
        (topo / "core_id").write_text(f"{core_id}\n")


def _cpu_info(tmp_path, sys_cpu, model="Test Model"):
    proc = tmp_path / "cpuinfo"
    proc.write_text(f"processor\t: 0\nmodel name\t: {model}\nflags\t: fpu vme\n")
    return cpu_info_impl(sys_cpu_root=str(sys_cpu), proc_cpuinfo=str(proc))


def test_consecutive_smt_4c8t(tmp_path):
    sys_cpu = tmp_path / "cpu"
    for cpu, (siblings, cid) in {
        0: ("0-1", 0),
        1: ("0-1", 0),
        2: ("2-3", 1),
        3: ("2-3", 1),
        4: ("4-5", 2),
        5: ("4-5", 2),
        6: ("6-7", 3),
        7: ("6-7", 3),
    }.items():
        _write_cpu(sys_cpu, cpu, siblings, core_id=cid)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["cpu_model"] == "Test Model"
    assert info["physical_core_count"] == 4
    assert info["logical_to_phys"] == {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3}
    assert info["phys_to_core_id"] == {0: 0, 1: 1, 2: 2, 3: 3}
    assert info["phys_to_package"] == {0: 0, 1: 0, 2: 0, 3: 0}
    assert info["phys_to_die"] == {0: 0, 1: 0, 2: 0, 3: 0}


def test_non_consecutive_smt_4c8t(tmp_path):
    sys_cpu = tmp_path / "cpu"
    for cpu, (siblings, cid) in {
        0: ("0,4", 0),
        4: ("0,4", 0),
        1: ("1,5", 1),
        5: ("1,5", 1),
        2: ("2,6", 2),
        6: ("2,6", 2),
        3: ("3,7", 3),
        7: ("3,7", 3),
    }.items():
        _write_cpu(sys_cpu, cpu, siblings, core_id=cid)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["physical_core_count"] == 4
    assert info["logical_to_phys"] == {0: 0, 4: 0, 1: 1, 5: 1, 2: 2, 6: 2, 3: 3, 7: 3}


def test_smt_disabled(tmp_path):
    sys_cpu = tmp_path / "cpu"
    for cpu in range(4):
        _write_cpu(sys_cpu, cpu, str(cpu), core_id=cpu)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["physical_core_count"] == 4
    assert info["logical_to_phys"] == {0: 0, 1: 1, 2: 2, 3: 3}


def test_4way_smt_single_core(tmp_path):
    sys_cpu = tmp_path / "cpu"
    for cpu in range(4):
        _write_cpu(sys_cpu, cpu, "0-3", core_id=0)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["physical_core_count"] == 1
    assert info["logical_to_phys"] == {0: 0, 1: 0, 2: 0, 3: 0}


def test_dual_socket(tmp_path):
    sys_cpu = tmp_path / "cpu"
    _write_cpu(sys_cpu, 0, "0", package_id=0, core_id=0)
    _write_cpu(sys_cpu, 1, "1", package_id=0, core_id=1)
    _write_cpu(sys_cpu, 2, "2", package_id=1, core_id=0)
    _write_cpu(sys_cpu, 3, "3", package_id=1, core_id=1)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["phys_to_package"] == {0: 0, 1: 0, 2: 1, 3: 1}
    assert info["phys_to_core_id"] == {0: 0, 1: 1, 2: 0, 3: 1}


def test_missing_die_and_core_default_to_zero(tmp_path):
    sys_cpu = tmp_path / "cpu"
    _write_cpu(sys_cpu, 0, "0", package_id=0, write_die=False, write_core=False)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["phys_to_die"] == {0: 0}
    assert info["phys_to_core_id"] == {0: 0}


def test_negative_package_normalized_to_zero(tmp_path):
    sys_cpu = tmp_path / "cpu"
    _write_cpu(sys_cpu, 0, "0", package_id=-1, die_id=-1, core_id=-1)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["phys_to_package"] == {0: 0}
    assert info["phys_to_die"] == {0: 0}
    assert info["phys_to_core_id"] == {0: 0}


def test_non_numeric_subdirs_skipped(tmp_path):
    sys_cpu = tmp_path / "cpu"
    _write_cpu(sys_cpu, 0, "0", core_id=0)
    (sys_cpu / "cpufreq").mkdir()
    (sys_cpu / "cpuidle").mkdir()

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["physical_core_count"] == 1


def test_mixed_separators(tmp_path):
    sys_cpu = tmp_path / "cpu"
    _write_cpu(sys_cpu, 0, "0,2-3", core_id=0)

    info = _cpu_info(tmp_path, sys_cpu)

    assert info["physical_core_count"] == 1
    assert info["logical_to_phys"] == {0: 0, 2: 0, 3: 0}


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0", [0]),
        ("0-3", [0, 1, 2, 3]),
        ("0,2-3", [0, 2, 3]),
        ("0,8", [0, 8]),
        ("", []),
    ],
)
def test_parse_cpulist(value, expected):
    assert _parse_cpulist(value) == expected


def test_parse_cpulist_malformed_raises():
    with pytest.raises(ValueError):
        _parse_cpulist("abc")


@pytest.mark.parametrize(
    "data,key,expected",
    [
        ({"Tccd1": 0.0}, "Tccd1", 0.0),
        ({"Tctl": 50}, "Tctl", 50.0),
        ({"x": "nan"}, "x", None),
        ({}, "missing", None),
    ],
)
def test_numeric(data, key, expected):
    assert _numeric(data, key) == expected
