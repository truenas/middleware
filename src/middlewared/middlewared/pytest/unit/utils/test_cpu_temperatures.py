from unittest.mock import patch

from middlewared.utils.cpu import read_cpu_temps, get_cpu_temperatures


def make_cpu_info(logical_to_phys, phys_to_package, phys_to_die, phys_to_core_id,
                  core_count, cpu_model='Test CPU'):
    return {
        'cpu_model': cpu_model,
        'core_count': core_count,
        'physical_core_count': len(phys_to_package),
        'logical_to_phys': logical_to_phys,
        'phys_to_package': phys_to_package,
        'phys_to_die': phys_to_die,
        'phys_to_core_id': phys_to_core_id,
    }


@patch('middlewared.utils.cpu.sensors')
def test_read_temps_multiple_chips(mock_sensors):
    """Test reading temperatures from dual socket Intel system"""
    mock_sensors.get_cpu_temperatures.return_value = {
        'coretemp-isa-0000': {'Package id 0': 36.0, 'Core 0': 48.0, 'Core 1': 49.0},
        'coretemp-isa-0001': {'Package id 1': 45.0, 'Core 0': 55.0, 'Core 1': 54.0},
    }

    result = read_cpu_temps()

    assert result == {
        'coretemp-isa-0000': {'Package id 0': 36.0, 'Core 0': 48.0, 'Core 1': 49.0},
        'coretemp-isa-0001': {'Package id 1': 45.0, 'Core 0': 55.0, 'Core 1': 54.0},
    }


@patch('middlewared.utils.cpu.sensors')
def test_read_temps_error_handling(mock_sensors):
    """Test that read_cpu_temps handles errors gracefully"""
    mock_sensors.get_cpu_temperatures.side_effect = OSError('Could not find libsensors')

    result = read_cpu_temps()

    assert result == {}


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_intel_consecutive_smt(mock_read_temps, mock_cpu_info):
    """Intel 4c/8t, consecutive SMT enumeration (cpu0/cpu1 share a core).

    This is the layout the old ht_map mirror loop mishandled: it double-counted
    the even physical cores and reported ~1.5x. The physical-core mean must be
    correct here.
    """
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3},
        phys_to_package={0: 0, 1: 0, 2: 0, 3: 0},
        phys_to_die={0: 0, 1: 0, 2: 0, 3: 0},
        phys_to_core_id={0: 0, 1: 1, 2: 2, 3: 3},
        core_count=8,
        cpu_model='Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz',
    )
    mock_read_temps.return_value = {
        'coretemp-isa-0000': {
            'Package id 0': 45.0, 'Core 0': 48.0, 'Core 1': 49.0, 'Core 2': 47.0, 'Core 3': 50.0,
        }
    }

    assert get_cpu_temperatures() == {
        'cpu0': 48.0, 'cpu1': 48.0, 'cpu2': 49.0, 'cpu3': 49.0,
        'cpu4': 47.0, 'cpu5': 47.0, 'cpu6': 50.0, 'cpu7': 50.0,
        'cpu': 48.5,
    }


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_intel_i5_12400_consecutive_smt_live(mock_read_temps, mock_cpu_info):
    """The reporter's box: i5-12400 6c/12t consecutive SMT, live LOAD sample.

    The buggy widget read 100 for this sample; the correct physical-core mean
    is (67+67+65+68+69+68)/6 = 67.33.
    """
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={i: i // 2 for i in range(12)},
        phys_to_package={i: 0 for i in range(6)},
        phys_to_die={i: 0 for i in range(6)},
        phys_to_core_id={i: i for i in range(6)},
        core_count=12,
        cpu_model='12th Gen Intel(R) Core(TM) i5-12400',
    )
    mock_read_temps.return_value = {
        'coretemp-isa-0000': {
            'Package id 0': 69.0,
            'Core 0': 67.0, 'Core 1': 67.0, 'Core 2': 65.0,
            'Core 3': 68.0, 'Core 4': 69.0, 'Core 5': 68.0,
        }
    }

    result = get_cpu_temperatures()

    assert result['cpu'] == (67.0 + 67.0 + 65.0 + 68.0 + 69.0 + 68.0) / 6
    # every one of the 12 logical CPUs is populated (the old code left cpu6..11 empty)
    assert set(result) == {f'cpu{i}' for i in range(12)} | {'cpu'}
    assert result['cpu0'] == result['cpu1'] == 67.0
    assert result['cpu10'] == result['cpu11'] == 68.0


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_intel_dual_socket(mock_read_temps, mock_cpu_info):
    """Dual-socket Xeon, no SMT: each chip's package resolved from its own
    'Package id N' label, so Core 0 on each socket lands on distinct cores."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={0: 0, 1: 1, 2: 2, 3: 3},
        phys_to_package={0: 0, 1: 0, 2: 1, 3: 1},
        phys_to_die={0: 0, 1: 0, 2: 0, 3: 0},
        phys_to_core_id={0: 0, 1: 1, 2: 0, 3: 1},
        core_count=4,
        cpu_model='Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
    )
    mock_read_temps.return_value = {
        'coretemp-isa-0000': {'Package id 0': 36.0, 'Core 0': 48.0, 'Core 1': 49.0},
        'coretemp-isa-0001': {'Package id 1': 45.0, 'Core 0': 55.0, 'Core 1': 54.0},
    }

    assert get_cpu_temperatures() == {
        'cpu0': 48.0, 'cpu1': 49.0, 'cpu2': 55.0, 'cpu3': 54.0, 'cpu': 51.5,
    }


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_intel_hybrid_pe_noncontiguous_core_id(mock_read_temps, mock_cpu_info):
    """Hybrid P+E: E-cores carry non-contiguous core_ids. Attribution is by
    core_id dict lookup, so gaps don't misassign."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={i: i for i in range(8)},
        phys_to_package={i: 0 for i in range(8)},
        phys_to_die={i: 0 for i in range(8)},
        phys_to_core_id={0: 0, 1: 1, 2: 2, 3: 3, 4: 8, 5: 9, 6: 10, 7: 11},
        core_count=8,
        cpu_model='12th Gen Intel(R) Core(TM) i9-12900K',
    )
    mock_read_temps.return_value = {
        'coretemp-isa-0000': {
            'Package id 0': 70.0,
            'Core 0': 60.0, 'Core 1': 62.0, 'Core 2': 64.0, 'Core 3': 66.0,
            'Core 8': 68.0, 'Core 9': 70.0, 'Core 10': 68.0, 'Core 11': 70.0,
        }
    }

    assert get_cpu_temperatures() == {
        'cpu0': 60.0, 'cpu1': 62.0, 'cpu2': 64.0, 'cpu3': 66.0,
        'cpu4': 68.0, 'cpu5': 70.0, 'cpu6': 68.0, 'cpu7': 70.0,
        'cpu': 66.0,
    }


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_amd_single_ccd(mock_read_temps, mock_cpu_info):
    """AMD Ryzen 5 3600, single CCD, 6c/12t: Tccd1 wins over the Tctl/Tdie
    package fallback."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={i: i // 2 for i in range(12)},
        phys_to_package={i: 0 for i in range(6)},
        phys_to_die={i: 0 for i in range(6)},
        phys_to_core_id={i: i for i in range(6)},
        core_count=12,
        cpu_model='AMD Ryzen 5 3600 6-Core Processor',
    )
    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {'Tctl': 48.625, 'Tdie': 48.625, 'Tccd1': 54.750},
    }

    assert get_cpu_temperatures() == {f'cpu{i}': 54.750 for i in range(12)} | {'cpu': 54.750}


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_amd_dual_ccd(mock_read_temps, mock_cpu_info):
    """AMD 3950X, two CCDs, 16c/32t: Tccd1->die0, Tccd2->die1 by die_id."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={i: i // 2 for i in range(32)},
        phys_to_package={i: 0 for i in range(16)},
        phys_to_die={i: (0 if i < 8 else 1) for i in range(16)},
        phys_to_core_id={i: i for i in range(16)},
        core_count=32,
        cpu_model='AMD Ryzen 9 3950X 16-Core Processor',
    )
    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {'Tctl': 50.0, 'Tdie': 48.0, 'Tccd1': 52.0, 'Tccd2': 54.0},
    }

    result = get_cpu_temperatures()

    assert result['cpu'] == 53.0
    for logical in range(16):  # die0 -> 52
        assert result[f'cpu{logical}'] == 52.0
    for logical in range(16, 32):  # die1 -> 54
        assert result[f'cpu{logical}'] == 54.0


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_amd_asymmetric_ccd(mock_read_temps, mock_cpu_info):
    """Asymmetric CCDs (die0=4 cores, die1=8 cores): no even-split assumption,
    aggregate is the plain mean over 12 physical cores."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={i: i for i in range(12)},
        phys_to_package={i: 0 for i in range(12)},
        phys_to_die={i: (0 if i < 4 else 1) for i in range(12)},
        phys_to_core_id={i: i for i in range(12)},
        core_count=12,
        cpu_model='AMD Ryzen 9 5900X 12-Core Processor',
    )
    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {'Tctl': 50.0, 'Tccd1': 52.0, 'Tccd2': 54.0},
    }

    result = get_cpu_temperatures()

    assert result['cpu'] == (52.0 * 4 + 54.0 * 8) / 12
    assert [result[f'cpu{i}'] for i in range(4)] == [52.0] * 4
    assert [result[f'cpu{i}'] for i in range(4, 12)] == [54.0] * 8


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_amd_prefer_tdie(mock_read_temps, mock_cpu_info):
    """Threadripper 1950X: Tdie preferred over Tctl (offset) and Tccd."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={i: i // 2 for i in range(32)},
        phys_to_package={i: 0 for i in range(16)},
        phys_to_die={i: 0 for i in range(16)},
        phys_to_core_id={i: i for i in range(16)},
        core_count=32,
        cpu_model='AMD Ryzen Threadripper 1950X 16-Core Processor',
    )
    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {'Tctl': 67.0, 'Tdie': 40.0, 'Tccd1': 65.5},
    }

    assert get_cpu_temperatures() == {f'cpu{i}': 40.0 for i in range(32)} | {'cpu': 40.0}


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_amd_dual_socket(mock_read_temps, mock_cpu_info):
    """Dual-socket EPYC: two k10temp chips resolved to distinct packages by
    alphabetical PCI-name index, so socket-0 readings don't overwrite socket-1."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={i: i for i in range(8)},
        phys_to_package={0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 1},
        phys_to_die={i: 0 for i in range(8)},
        phys_to_core_id={0: 0, 1: 1, 2: 2, 3: 3, 4: 0, 5: 1, 6: 2, 7: 3},
        core_count=8,
        cpu_model='AMD EPYC 7302 16-Core Processor',
    )
    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {'Tctl': 60.0},
        'k10temp-pci-00cb': {'Tctl': 70.0},
    }

    assert get_cpu_temperatures() == {
        'cpu0': 60.0, 'cpu1': 60.0, 'cpu2': 60.0, 'cpu3': 60.0,
        'cpu4': 70.0, 'cpu5': 70.0, 'cpu6': 70.0, 'cpu7': 70.0,
        'cpu': 65.0,
    }


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_arm_4way_smt_generic_sensor(mock_read_temps, mock_cpu_info):
    """ARM/generic cpu_thermal single sensor, 4-way SMT single core: temp1 is
    broadcast to the physical core and projected to all four siblings."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={0: 0, 1: 0, 2: 0, 3: 0},
        phys_to_package={0: 0},
        phys_to_die={0: 0},
        phys_to_core_id={0: 0},
        core_count=4,
        cpu_model=None,
    )
    mock_read_temps.return_value = {'cpu_thermal-virtual-0': {'temp1': 70.0}}

    assert get_cpu_temperatures() == {
        'cpu0': 70.0, 'cpu1': 70.0, 'cpu2': 70.0, 'cpu3': 70.0, 'cpu': 70.0,
    }


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_no_sensors_fallback(mock_read_temps, mock_cpu_info):
    """No readable sensors: emit the all-zero shape (core_count logicals + cpu)."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={0: 0, 1: 1, 2: 2, 3: 3},
        phys_to_package={0: 0, 1: 0, 2: 0, 3: 0},
        phys_to_die={0: 0, 1: 0, 2: 0, 3: 0},
        phys_to_core_id={0: 0, 1: 1, 2: 2, 3: 3},
        core_count=4,
    )
    mock_read_temps.return_value = {}

    assert get_cpu_temperatures() == {
        'cpu0': 0.0, 'cpu1': 0.0, 'cpu2': 0.0, 'cpu3': 0.0, 'cpu': 0.0,
    }


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_amd_zero_tccd_preserved(mock_read_temps, mock_cpu_info):
    """A legitimate 0.0 CCD reading must be kept (the old `Tccd and v` truthiness
    check dropped it). Mixed 0.0/50.0 dies also prove this is the real reading
    path, not the all-zero fallback."""
    mock_cpu_info.return_value = make_cpu_info(
        logical_to_phys={0: 0, 1: 0, 2: 1, 3: 1},
        phys_to_package={0: 0, 1: 0},
        phys_to_die={0: 0, 1: 1},
        phys_to_core_id={0: 0, 1: 1},
        core_count=4,
        cpu_model='AMD Ryzen 5 5600 6-Core Processor',
    )
    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {'Tctl': 50.0, 'Tccd1': 0.0, 'Tccd2': 50.0},
    }

    assert get_cpu_temperatures() == {
        'cpu0': 0.0, 'cpu1': 0.0, 'cpu2': 50.0, 'cpu3': 50.0, 'cpu': 25.0,
    }
