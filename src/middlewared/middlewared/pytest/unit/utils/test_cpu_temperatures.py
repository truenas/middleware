from unittest.mock import patch

from middlewared.utils.cpu import read_cpu_temps, get_cpu_temperatures


@patch('middlewared.utils.cpu.sensors')
def test_read_temps_multiple_chips(mock_sensors):
    """Test reading temperatures from dual socket Intel system"""
    # Mock get_cpu_temperatures to return dual socket Intel data
    # Using realistic chip names from libsensors (with bus info, not hwmon)
    mock_sensors.get_cpu_temperatures.return_value = {
        'coretemp-isa-0000': {
            'Package id 0': 36.0,
            'Core 0': 48.0,
            'Core 1': 49.0
        },
        'coretemp-isa-0001': {
            'Package id 1': 45.0,
            'Core 0': 55.0,
            'Core 1': 54.0
        }
    }

    result = read_cpu_temps()

    assert result == {
        'coretemp-isa-0000': {
            'Package id 0': 36.0,
            'Core 0': 48.0,
            'Core 1': 49.0
        },
        'coretemp-isa-0001': {
            'Package id 1': 45.0,
            'Core 0': 55.0,
            'Core 1': 54.0
        }
    }


@patch('middlewared.utils.cpu.sensors')
def test_read_temps_error_handling(mock_sensors):
    """Test that read_cpu_temps handles errors gracefully"""
    mock_sensors.get_cpu_temperatures.side_effect = OSError('Could not find libsensors')

    result = read_cpu_temps()

    assert result == {}


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_intel(mock_read_temps, mock_cpu_info):
    """Test Intel CPU temperature processing with hyperthreading"""
    mock_cpu_info.return_value = {
        'cpu_model': 'Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz',
        'core_count': 8,
        'physical_core_count': 4,
        'ht_map': {'cpu0': 'cpu4', 'cpu1': 'cpu5', 'cpu2': 'cpu6', 'cpu3': 'cpu7'}
    }

    mock_read_temps.return_value = {
        'coretemp-isa-0000': {
            'Package id 0': 45.0,
            'Core 0': 48.0,
            'Core 1': 49.0,
            'Core 2': 47.0,
            'Core 3': 50.0
        }
    }

    result = get_cpu_temperatures()

    expected = {
        'cpu0': 48.0,
        'cpu1': 49.0,
        'cpu2': 47.0,
        'cpu3': 50.0,
        'cpu4': 48.0,  # HT copy of cpu0
        'cpu5': 49.0,  # HT copy of cpu1
        'cpu6': 47.0,  # HT copy of cpu2
        'cpu7': 50.0,  # HT copy of cpu3
        'cpu': 48.5    # Average
    }

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_amd_with_ccd(mock_read_temps, mock_cpu_info):
    """Test AMD Ryzen with CCD temperature"""
    mock_cpu_info.return_value = {
        'cpu_model': 'AMD Ryzen 5 3600 6-Core Processor',
        'core_count': 12,
        'physical_core_count': 6,
        'ht_map': {
            'cpu0': 'cpu6', 'cpu1': 'cpu7', 'cpu2': 'cpu8',
            'cpu3': 'cpu9', 'cpu4': 'cpu10', 'cpu5': 'cpu11'
        }
    }

    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {
            'Tctl': 48.625,
            'Tdie': 48.625,
            'Tccd1': 54.750
        }
    }

    result = get_cpu_temperatures()

    # All cores should use Tccd1 temperature
    expected = {f'cpu{i}': 54.750 for i in range(12)}
    expected['cpu'] = 54.750

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_amd_prefer_tdie(mock_read_temps, mock_cpu_info):
    """Test AMD Threadripper that prefers Tdie over Tctl"""
    mock_cpu_info.return_value = {
        'cpu_model': 'AMD Ryzen Threadripper 1950X 16-Core Processor',
        'core_count': 32,
        'physical_core_count': 16,
        'ht_map': {f'cpu{i}': f'cpu{i+16}' for i in range(16)}
    }

    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {
            'Tctl': 67.0,
            'Tdie': 40.0,
            'Tccd1': 65.5
        }
    }

    result = get_cpu_temperatures()

    # All cores should use Tdie (40.0) due to AMD_PREFER_TDIE
    expected = {f'cpu{i}': 40.0 for i in range(32)}
    expected['cpu'] = 40.0

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_amd_multiple_ccds(mock_read_temps, mock_cpu_info):
    """Test AMD CPU with multiple CCDs (chiplet design)"""
    mock_cpu_info.return_value = {
        'cpu_model': 'AMD Ryzen 9 3950X 16-Core Processor',
        'core_count': 32,
        'physical_core_count': 16,
        'ht_map': {f'cpu{i}': f'cpu{i+16}' for i in range(16)}
    }

    mock_read_temps.return_value = {
        'k10temp-pci-00c3': {
            'Tctl': 50.0,
            'Tdie': 48.0,
            'Tccd1': 52.0,
            'Tccd2': 54.0
        }
    }

    result = get_cpu_temperatures()

    # With 2 CCDs and 16 cores, each CCD handles 8 cores
    expected = {}
    for i in range(8):
        expected[f'cpu{i}'] = 52.0  # Tccd1
        expected[f'cpu{i+16}'] = 52.0  # HT of Tccd1
    for i in range(8, 16):
        expected[f'cpu{i}'] = 54.0  # Tccd2
        expected[f'cpu{i+16}'] = 54.0  # HT of Tccd2
    expected['cpu'] = 53.0  # Average

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_dual_socket_intel(mock_read_temps, mock_cpu_info):
    """Test dual socket Intel Xeon system"""
    mock_cpu_info.return_value = {
        'cpu_model': 'Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
        'core_count': 4,
        'physical_core_count': 4,
        'ht_map': {}
    }

    mock_read_temps.return_value = {
        'coretemp-isa-0000': {
            'Package id 0': 36.0,
            'Core 0': 48.0,
            'Core 1': 49.0
        },
        'coretemp-isa-0001': {
            'Package id 1': 45.0,
            'Core 0': 55.0,
            'Core 1': 54.0
        }
    }

    result = get_cpu_temperatures()

    expected = {
        'cpu0': 48.0,
        'cpu1': 49.0,
        'cpu2': 55.0,
        'cpu3': 54.0,
        'cpu': 51.5
    }

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_no_temps_found(mock_read_temps, mock_cpu_info):
    """Test fallback when no temperature readings are available"""
    mock_cpu_info.return_value = {
        'cpu_model': 'Unknown CPU',
        'core_count': 4,
        'physical_core_count': 4,
        'ht_map': {}
    }

    mock_read_temps.return_value = {}

    result = get_cpu_temperatures()

    # Should return 0 for all CPUs when no temps available
    expected = {
        'cpu0': 0,
        'cpu1': 0,
        'cpu2': 0,
        'cpu3': 0,
        'cpu': 0
    }

    assert result == expected
