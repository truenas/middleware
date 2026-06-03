import json
import subprocess
from unittest.mock import patch, MagicMock

from middlewared.utils.metrics.gpu_usage import (
    get_gpu_usage, _get_nvidia_gpu_usage, _get_amd_gpu_usage, _get_intel_gpu_usage,
)

NVIDIA_SMI_OUTPUT = (
    '0, NVIDIA GeForce RTX 3080, 45, 30, 10240, 3072, 7168, 65, 55, 220.50\n'
    '1, NVIDIA GeForce RTX 3070, 12, 8, 8192, 1024, 7168, 58, 40, 180.25\n'
)

NVIDIA_SMI_OUTPUT_UNAVAILABLE = (
    '0, NVIDIA Tesla T4, 30, 15, 15360, 2048, 13312, 52, [Not Supported], 70.00\n'
)

ROCM_SMI_JSON_OUTPUT = json.dumps({
    'card0': {
        'GPU use (%)': '45',
        'GPU memory use (%)': '30',
        'Temperature (Sensor edge) (C)': '65',
        'Temperature (Sensor junction) (C)': '75',
        'Average Graphics Package Power (W)': '220.50',
        'Fan Speed (%)': '55',
        'Card Series': 'Radeon RX 7900 XT',
        'Card Model': '0x744c',
        'VRAM Total Memory (B)': '21458059264',
        'VRAM Total Used Memory (B)': '3221225472',
    },
    'card1': {
        'GPU use (%)': '12',
        'GPU memory use (%)': '8',
        'Temperature (Sensor edge) (C)': '58',
        'Average Graphics Package Power (W)': '180.25',
        'Fan Speed (%)': '40',
        'Card Series': 'Radeon RX 7800 XT',
        'VRAM Total Memory (B)': '17179869184',
        'VRAM Total Used Memory (B)': '1073741824',
    },
})

XPU_SMI_DISCOVERY_DUMP = (
    'Device ID,Device Name,Memory Physical Size\n'
    '0,"Intel Data Center GPU Flex 170","15258 MiB"\n'
    '1,"Intel Arc A770","15258 MiB"\n'
)

XPU_SMI_DUMP_OUTPUT = (
    'Timestamp, DeviceId, GPU Utilization (%), GPU Power (W), GPU Core Temperature (C), '
    'GPU Memory Utilization (%), GPU Memory Used (MiB)\n'
    '06:14:46.000,    0, 35.00, 120.50, 55, 40.00, 4096\n'
    '06:14:46.000,    1, 10.00, 80.25, 42, 15.00, 2048\n'
)


def test_get_gpu_usage_nvidia():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = NVIDIA_SMI_OUTPUT

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/usr/bin/nvidia-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', return_value=mock_result):
        result = get_gpu_usage()

    assert 'gpu0' in result
    assert 'gpu1' in result
    assert result['gpu0'] == {
        'index': 0,
        'name': 'NVIDIA GeForce RTX 3080',
        'gpu_utilization': 45.0,
        'memory_utilization': 30.0,
        'memory_total': 10240,
        'memory_used': 3072,
        'memory_free': 7168,
        'temperature': 65,
        'fan_speed': 55,
        'power_draw': 220.50,
    }
    assert result['gpu1']['index'] == 1
    assert result['gpu1']['name'] == 'NVIDIA GeForce RTX 3070'
    assert result['gpu1']['gpu_utilization'] == 12.0


def test_get_gpu_usage_no_nvidia_smi():
    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value=None):
        result = get_gpu_usage()

    assert result == {}


def test_get_gpu_usage_nvidia_smi_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ''

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/usr/bin/nvidia-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', return_value=mock_result):
        result = get_gpu_usage()

    assert result == {}


def test_get_gpu_usage_unsupported_fields():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = NVIDIA_SMI_OUTPUT_UNAVAILABLE

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/usr/bin/nvidia-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', return_value=mock_result):
        result = _get_nvidia_gpu_usage()

    assert 'gpu0' in result
    assert result['gpu0']['fan_speed'] is None
    assert result['gpu0']['gpu_utilization'] == 30.0
    assert result['gpu0']['temperature'] == 52


def test_get_gpu_usage_timeout():
    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/usr/bin/nvidia-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', side_effect=subprocess.TimeoutExpired('nvidia-smi', 5)):
        result = get_gpu_usage()

    assert result == {}


def test_get_amd_gpu_usage():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ROCM_SMI_JSON_OUTPUT

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/opt/rocm/bin/rocm-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', return_value=mock_result):
        result = _get_amd_gpu_usage()

    assert 'gpu0' in result
    assert 'gpu1' in result
    assert result['gpu0']['index'] == 0
    assert result['gpu0']['name'] == 'Radeon RX 7900 XT'
    assert result['gpu0']['gpu_utilization'] == 45.0
    assert result['gpu0']['memory_utilization'] == 30.0
    assert result['gpu0']['memory_total'] == 20464
    assert result['gpu0']['memory_used'] == 3072
    assert result['gpu0']['memory_free'] == 20464 - 3072
    assert result['gpu0']['temperature'] == 65
    assert result['gpu0']['fan_speed'] == 55
    assert result['gpu0']['power_draw'] == 220.50
    assert result['gpu1']['name'] == 'Radeon RX 7800 XT'
    assert result['gpu1']['gpu_utilization'] == 12.0


def test_get_amd_gpu_usage_no_rocm_smi():
    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value=None):
        result = _get_amd_gpu_usage()

    assert result == {}


def test_get_amd_gpu_usage_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ''

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/opt/rocm/bin/rocm-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', return_value=mock_result):
        result = _get_amd_gpu_usage()

    assert result == {}


def test_get_amd_gpu_usage_invalid_json():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = 'not valid json'

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/opt/rocm/bin/rocm-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', return_value=mock_result):
        result = _get_amd_gpu_usage()

    assert result == {}


def test_get_amd_gpu_usage_missing_fields():
    """Test AMD GPU parsing when some fields are missing from JSON."""
    sparse_data = json.dumps({
        'card0': {
            'GPU use (%)': '50',
            'Card Series': 'AMD Instinct MI250',
        },
    })
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = sparse_data

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/opt/rocm/bin/rocm-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', return_value=mock_result):
        result = _get_amd_gpu_usage()

    assert 'gpu0' in result
    assert result['gpu0']['gpu_utilization'] == 50.0
    assert result['gpu0']['name'] == 'AMD Instinct MI250'
    assert result['gpu0']['temperature'] is None
    assert result['gpu0']['power_draw'] is None
    assert result['gpu0']['memory_total'] is None


def test_get_intel_gpu_usage():
    mock_discovery = MagicMock()
    mock_discovery.returncode = 0
    mock_discovery.stdout = XPU_SMI_DISCOVERY_DUMP

    mock_dump = MagicMock()
    mock_dump.returncode = 0
    mock_dump.stdout = XPU_SMI_DUMP_OUTPUT

    def run_side_effect(cmd):
        if 'discovery' in cmd:
            return mock_discovery
        return mock_dump

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/usr/bin/xpu-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', side_effect=run_side_effect):
        result = _get_intel_gpu_usage()

    assert 'gpu0' in result
    assert 'gpu1' in result
    assert result['gpu0']['index'] == 0
    assert result['gpu0']['name'] == 'Intel Data Center GPU Flex 170'
    assert result['gpu0']['gpu_utilization'] == 35.0
    assert result['gpu0']['power_draw'] == 120.50
    assert result['gpu0']['temperature'] == 55
    assert result['gpu0']['memory_utilization'] == 40.0
    assert result['gpu0']['memory_used'] == 4096
    assert result['gpu1']['name'] == 'Intel Arc A770'
    assert result['gpu1']['gpu_utilization'] == 10.0


def test_get_intel_gpu_usage_no_xpu_smi():
    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value=None):
        result = _get_intel_gpu_usage()

    assert result == {}


def test_get_intel_gpu_usage_dump_failure():
    mock_discovery = MagicMock()
    mock_discovery.returncode = 0
    mock_discovery.stdout = XPU_SMI_DISCOVERY_DUMP

    mock_dump = MagicMock()
    mock_dump.returncode = 1
    mock_dump.stdout = ''

    def run_side_effect(cmd):
        if 'discovery' in cmd:
            return mock_discovery
        return mock_dump

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/usr/bin/xpu-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', side_effect=run_side_effect):
        result = _get_intel_gpu_usage()

    assert result == {}


def test_get_intel_gpu_usage_discovery_failure():
    """Test Intel GPU parsing when discovery fails but dump works."""
    mock_discovery = MagicMock()
    mock_discovery.returncode = 1
    mock_discovery.stdout = ''

    mock_dump = MagicMock()
    mock_dump.returncode = 0
    mock_dump.stdout = XPU_SMI_DUMP_OUTPUT

    def run_side_effect(cmd):
        if 'discovery' in cmd:
            return mock_discovery
        return mock_dump

    with patch('middlewared.utils.metrics.gpu_usage.shutil.which', return_value='/usr/bin/xpu-smi'), \
         patch('middlewared.utils.metrics.gpu_usage.subprocess.run', side_effect=run_side_effect):
        result = _get_intel_gpu_usage()

    assert 'gpu0' in result
    assert result['gpu0']['name'] == 'Intel GPU 0'
    assert result['gpu0']['gpu_utilization'] == 35.0
