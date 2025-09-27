from pathlib import Path
from unittest.mock import patch, MagicMock

from middlewared.utils.cpu import read_cpu_temps, get_cpu_temperatures


@patch('middlewared.utils.cpu.HWMON_ROOT')
def test_read_intel_coretemp(mock_hwmon_root):
    mock_hwmon0 = MagicMock(spec=Path)
    mock_hwmon0.name = 'hwmon0'
    mock_hwmon1 = MagicMock(spec=Path)
    mock_hwmon1.name = 'hwmon1'

    mock_hwmon_root.glob.return_value = [mock_hwmon0, mock_hwmon1]

    # Setup hwmon0 as coretemp for Intel CPUs
    name_path0 = MagicMock()
    name_path0.read_text.return_value = 'coretemp\n'

    # Setup temperature input files
    temp1_input = MagicMock(spec=Path)
    temp1_input.stem = 'temp1'
    temp2_input = MagicMock(spec=Path)
    temp2_input.stem = 'temp2'
    temp3_input = MagicMock(spec=Path)
    temp3_input.stem = 'temp3'

    def hwmon0_side_effect(pattern):
        if pattern == 'temp*_input':
            return [temp1_input, temp2_input, temp3_input]
        return []

    mock_hwmon0.glob.side_effect = hwmon0_side_effect

    # Mock label files
    temp1_label = MagicMock()
    temp1_label.exists.return_value = True
    temp1_label.read_text.return_value = 'Package id 0\n'

    temp2_label = MagicMock()
    temp2_label.exists.return_value = True
    temp2_label.read_text.return_value = 'Core 0\n'

    temp3_label = MagicMock()
    temp3_label.exists.return_value = True
    temp3_label.read_text.return_value = 'Core 1\n'

    def hwmon0_div_effect(path):
        if path == 'name':
            return name_path0
        elif path == 'temp1_label':
            return temp1_label
        elif path == 'temp2_label':
            return temp2_label
        elif path == 'temp3_label':
            return temp3_label
        return MagicMock()

    mock_hwmon0.__truediv__.side_effect = hwmon0_div_effect

    # Mock temperature values (in millidegrees)
    temp1_input.read_text.return_value = '45000\n'
    temp2_input.read_text.return_value = '48000\n'
    temp3_input.read_text.return_value = '49000\n'

    # Setup hwmon1 as non-CPU sensor
    name_path1 = MagicMock()
    name_path1.read_text.return_value = 'acpitz\n'

    def hwmon1_div_effect(path):
        if path == 'name':
            return name_path1
        return MagicMock()

    mock_hwmon1.__truediv__.side_effect = hwmon1_div_effect

    result = read_cpu_temps()

    expected = {
        'coretemp-hwmon0': {
            'Package id 0': 45.0,
            'Core 0': 48.0,
            'Core 1': 49.0
        }
    }

    assert result == expected


@patch('middlewared.utils.cpu.HWMON_ROOT')
def test_read_amd_k10temp(mock_hwmon_root):
    mock_hwmon0 = MagicMock(spec=Path)
    mock_hwmon0.name = 'hwmon0'

    mock_hwmon_root.glob.return_value = [mock_hwmon0]

    # Setup hwmon0 as k10temp for AMD CPUs
    name_path0 = MagicMock()
    name_path0.read_text.return_value = 'k10temp\n'

    # Setup temperature input files
    temp1_input = MagicMock(spec=Path)
    temp1_input.stem = 'temp1'
    temp2_input = MagicMock(spec=Path)
    temp2_input.stem = 'temp2'
    temp3_input = MagicMock(spec=Path)
    temp3_input.stem = 'temp3'

    def hwmon0_side_effect(pattern):
        if pattern == 'temp*_input':
            return [temp1_input, temp2_input, temp3_input]
        return []

    mock_hwmon0.glob.side_effect = hwmon0_side_effect

    # Mock label files
    temp1_label = MagicMock()
    temp1_label.exists.return_value = True
    temp1_label.read_text.return_value = 'Tctl\n'

    temp2_label = MagicMock()
    temp2_label.exists.return_value = True
    temp2_label.read_text.return_value = 'Tdie\n'

    temp3_label = MagicMock()
    temp3_label.exists.return_value = True
    temp3_label.read_text.return_value = 'Tccd1\n'

    def hwmon0_div_effect(path):
        if path == 'name':
            return name_path0
        elif path == 'temp1_label':
            return temp1_label
        elif path == 'temp2_label':
            return temp2_label
        elif path == 'temp3_label':
            return temp3_label
        return MagicMock()

    mock_hwmon0.__truediv__.side_effect = hwmon0_div_effect

    # Mock temperature values (in millidegrees)
    temp1_input.read_text.return_value = '67000\n'
    temp2_input.read_text.return_value = '40000\n'
    temp3_input.read_text.return_value = '65500\n'

    result = read_cpu_temps()

    expected = {
        'k10temp-hwmon0': {
            'Tctl': 67.0,
            'Tdie': 40.0,
            'Tccd1': 65.5
        }
    }

    assert result == expected


@patch('middlewared.utils.cpu.HWMON_ROOT')
def test_read_temps_no_labels(mock_hwmon_root):
    mock_hwmon0 = MagicMock(spec=Path)
    mock_hwmon0.name = 'hwmon0'

    mock_hwmon_root.glob.return_value = [mock_hwmon0]

    # Setup hwmon0 as k10temp for AMD CPUs
    name_path0 = MagicMock()
    name_path0.read_text.return_value = 'k10temp\n'

    # Setup temperature input file
    temp1_input = MagicMock(spec=Path)
    temp1_input.stem = 'temp1'

    def hwmon0_side_effect(pattern):
        if pattern == 'temp*_input':
            return [temp1_input]
        return []

    mock_hwmon0.glob.side_effect = hwmon0_side_effect

    # No label file exists
    temp1_label = MagicMock()
    temp1_label.exists.return_value = False

    def hwmon0_div_effect(path):
        if path == 'name':
            return name_path0
        elif path == 'temp1_label':
            return temp1_label
        return MagicMock()

    mock_hwmon0.__truediv__.side_effect = hwmon0_div_effect

    # Mock temperature value
    temp1_input.read_text.return_value = '48230\n'

    result = read_cpu_temps()

    expected = {
        'k10temp-hwmon0': {
            'temp1': 48.23
        }
    }

    assert result == expected


@patch('middlewared.utils.cpu.HWMON_ROOT')
def test_read_temps_multiple_chips(mock_hwmon_root):
    mock_hwmon0 = MagicMock(spec=Path)
    mock_hwmon0.name = 'hwmon0'
    mock_hwmon1 = MagicMock(spec=Path)
    mock_hwmon1.name = 'hwmon1'

    mock_hwmon_root.glob.return_value = [mock_hwmon0, mock_hwmon1]

    # Setup hwmon0 as coretemp for socket 0
    name_path0 = MagicMock()
    name_path0.read_text.return_value = 'coretemp\n'

    temp1_input_0 = MagicMock(spec=Path)
    temp1_input_0.stem = 'temp1'
    temp2_input_0 = MagicMock(spec=Path)
    temp2_input_0.stem = 'temp2'

    def hwmon0_side_effect(pattern):
        if pattern == 'temp*_input':
            return [temp1_input_0, temp2_input_0]
        return []

    mock_hwmon0.glob.side_effect = hwmon0_side_effect

    temp1_label_0 = MagicMock()
    temp1_label_0.exists.return_value = True
    temp1_label_0.read_text.return_value = 'Package id 0\n'

    temp2_label_0 = MagicMock()
    temp2_label_0.exists.return_value = True
    temp2_label_0.read_text.return_value = 'Core 0\n'

    def hwmon0_div_effect(path):
        if path == 'name':
            return name_path0
        elif path == 'temp1_label':
            return temp1_label_0
        elif path == 'temp2_label':
            return temp2_label_0
        return MagicMock()

    mock_hwmon0.__truediv__.side_effect = hwmon0_div_effect

    temp1_input_0.read_text.return_value = '36000\n'
    temp2_input_0.read_text.return_value = '48000\n'

    # Setup hwmon1 as coretemp for socket 1
    name_path1 = MagicMock()
    name_path1.read_text.return_value = 'coretemp\n'

    temp1_input_1 = MagicMock(spec=Path)
    temp1_input_1.stem = 'temp1'
    temp2_input_1 = MagicMock(spec=Path)
    temp2_input_1.stem = 'temp2'

    def hwmon1_side_effect(pattern):
        if pattern == 'temp*_input':
            return [temp1_input_1, temp2_input_1]
        return []

    mock_hwmon1.glob.side_effect = hwmon1_side_effect

    temp1_label_1 = MagicMock()
    temp1_label_1.exists.return_value = True
    temp1_label_1.read_text.return_value = 'Package id 1\n'

    temp2_label_1 = MagicMock()
    temp2_label_1.exists.return_value = True
    temp2_label_1.read_text.return_value = 'Core 0\n'

    def hwmon1_div_effect(path):
        if path == 'name':
            return name_path1
        elif path == 'temp1_label':
            return temp1_label_1
        elif path == 'temp2_label':
            return temp2_label_1
        return MagicMock()

    mock_hwmon1.__truediv__.side_effect = hwmon1_div_effect

    temp1_input_1.read_text.return_value = '45000\n'
    temp2_input_1.read_text.return_value = '55000\n'

    result = read_cpu_temps()

    expected = {
        'coretemp-hwmon0': {
            'Package id 0': 36.0,
            'Core 0': 48.0
        },
        'coretemp-hwmon1': {
            'Package id 1': 45.0,
            'Core 0': 55.0
        }
    }

    assert result == expected


@patch('middlewared.utils.cpu.HWMON_ROOT')
def test_read_temps_file_errors(mock_hwmon_root):
    mock_hwmon0 = MagicMock(spec=Path)
    mock_hwmon0.name = 'hwmon0'

    mock_hwmon_root.glob.return_value = [mock_hwmon0]

    # Setup hwmon0 with FileNotFoundError
    name_path0 = MagicMock()
    name_path0.read_text.side_effect = FileNotFoundError()

    def hwmon0_div_effect(path):
        if path == 'name':
            return name_path0
        return MagicMock()

    mock_hwmon0.__truediv__.side_effect = hwmon0_div_effect

    result = read_cpu_temps()

    assert result == {}


@patch('middlewared.utils.cpu.HWMON_ROOT')
def test_read_temps_invalid_temperature_value(mock_hwmon_root):
    mock_hwmon0 = MagicMock(spec=Path)
    mock_hwmon0.name = 'hwmon0'

    mock_hwmon_root.glob.return_value = [mock_hwmon0]

    name_path0 = MagicMock()
    name_path0.read_text.return_value = 'coretemp\n'

    temp1_input = MagicMock(spec=Path)
    temp1_input.stem = 'temp1'

    def hwmon0_side_effect(pattern):
        if pattern == 'temp*_input':
            return [temp1_input]
        return []

    mock_hwmon0.glob.side_effect = hwmon0_side_effect

    temp1_label = MagicMock()
    temp1_label.exists.return_value = False

    def hwmon0_div_effect(path):
        if path == 'name':
            return name_path0
        elif path == 'temp1_label':
            return temp1_label
        return MagicMock()

    mock_hwmon0.__truediv__.side_effect = hwmon0_div_effect

    # Invalid temperature value
    temp1_input.read_text.return_value = 'invalid\n'

    result = read_cpu_temps()

    assert result == {}


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_intel(mock_read_temps, mock_cpu_info):
    # Mock Intel CPU configuration
    mock_cpu_info.return_value = {
        'cpu_model': 'Intel(R) Core(TM) i5-8250U CPU @ 1.60GHz',
        'core_count': 8,
        'physical_core_count': 4,
        'ht_map': {'cpu0': 'cpu4', 'cpu1': 'cpu5', 'cpu2': 'cpu6', 'cpu3': 'cpu7'}
    }

    mock_read_temps.return_value = {
        'coretemp-hwmon0': {
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
def test_get_temperatures_amd_ryzen(mock_read_temps, mock_cpu_info):
    # Mock AMD Ryzen configuration
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
        'k10temp-hwmon0': {
            'Tctl': 48.625,
            'Tdie': 48.625,
            'Tccd1': 54.750
        }
    }

    result = get_cpu_temperatures()

    expected = {
        'cpu0': 54.750,
        'cpu1': 54.750,
        'cpu2': 54.750,
        'cpu3': 54.750,
        'cpu4': 54.750,
        'cpu5': 54.750,
        'cpu6': 54.750,  # HT copies
        'cpu7': 54.750,
        'cpu8': 54.750,
        'cpu9': 54.750,
        'cpu10': 54.750,
        'cpu11': 54.750,
        'cpu': 54.750
    }

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_amd_threadripper_with_tdie(mock_read_temps, mock_cpu_info):
    # Mock AMD Threadripper configuration
    mock_cpu_info.return_value = {
        'cpu_model': 'AMD Ryzen Threadripper 1950X 16-Core Processor',
        'core_count': 32,
        'physical_core_count': 16,
        'ht_map': {f'cpu{i}': f'cpu{i+16}' for i in range(16)}
    }

    mock_read_temps.return_value = {
        'k10temp-hwmon0': {
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
    # Mock AMD CPU with multiple CCDs
    mock_cpu_info.return_value = {
        'cpu_model': 'AMD Ryzen 9 3950X 16-Core Processor',
        'core_count': 32,
        'physical_core_count': 16,
        'ht_map': {f'cpu{i}': f'cpu{i+16}' for i in range(16)}
    }

    mock_read_temps.return_value = {
        'k10temp-hwmon0': {
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
def test_get_temperatures_amd_no_label(mock_read_temps, mock_cpu_info):
    # Mock AMD CPU with no labels
    mock_cpu_info.return_value = {
        'cpu_model': 'AMD Opteron APU 1-Core Processor',
        'core_count': 1,
        'physical_core_count': 1,
        'ht_map': {}
    }

    mock_read_temps.return_value = {
        'k10temp-hwmon0': {
            'temp1': 48.23
        }
    }

    result = get_cpu_temperatures()

    expected = {
        'cpu0': 48.23,
        'cpu': 48.23
    }

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_dual_socket_intel(mock_read_temps, mock_cpu_info):
    # Mock dual socket Intel configuration
    mock_cpu_info.return_value = {
        'cpu_model': 'Intel(R) Xeon(R) CPU E5-2690 v4 @ 2.60GHz',
        'core_count': 4,
        'physical_core_count': 4,
        'ht_map': {}
    }

    mock_read_temps.return_value = {
        'coretemp-hwmon0': {
            'Package id 0': 36.0,
            'Core 0': 48.0,
            'Core 1': 49.0
        },
        'coretemp-hwmon1': {
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
    # Mock configuration with no temperature readings
    mock_cpu_info.return_value = {
        'cpu_model': 'Unknown CPU',
        'core_count': 4,
        'physical_core_count': 4,
        'ht_map': {}
    }

    mock_read_temps.return_value = {}

    result = get_cpu_temperatures()

    expected = {
        'cpu0': 0,
        'cpu1': 0,
        'cpu2': 0,
        'cpu3': 0,
        'cpu': 0
    }

    assert result == expected


@patch('middlewared.utils.cpu.cpu_info')
@patch('middlewared.utils.cpu.read_cpu_temps')
def test_get_temperatures_amd_only_tctl(mock_read_temps, mock_cpu_info):
    # Mock AMD CPU with only Tctl available
    mock_cpu_info.return_value = {
        'cpu_model': 'AMD CPU',
        'core_count': 4,
        'physical_core_count': 4,
        'ht_map': {}
    }

    mock_read_temps.return_value = {
        'k10temp-hwmon0': {
            'Tctl': 55.0
        }
    }

    result = get_cpu_temperatures()

    expected = {
        'cpu0': 55.0,
        'cpu1': 55.0,
        'cpu2': 55.0,
        'cpu3': 55.0,
        'cpu': 55.0
    }

    assert result == expected
