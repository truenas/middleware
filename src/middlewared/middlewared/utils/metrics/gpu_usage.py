import json
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

NVIDIA_SMI_QUERY_FIELDS = (
    'index',
    'name',
    'utilization.gpu',
    'utilization.memory',
    'memory.total',
    'memory.used',
    'memory.free',
    'temperature.gpu',
    'fan.speed',
    'power.draw',
)

# xpu-smi dump metric IDs:
# 0 = GPU Utilization (%)
# 1 = GPU Power (W)
# 3 = GPU Core Temperature (C)
# 5 = GPU Memory Utilization (%)
# 18 = GPU Memory Used (MiB)
XPU_SMI_METRIC_IDS = '0,1,3,5,18'

# xpu-smi discovery dump metric IDs:
# 0 = Device ID
# 1 = Device Name
# 16 = Memory Physical Size (MiB)
XPU_SMI_DISCOVERY_IDS = '0,1,16'


def get_gpu_usage() -> dict[str, dict]:
    """
    Retrieve GPU usage statistics from all supported GPU vendors.

    Attempts to query GPU metrics using nvidia-smi, rocm-smi, and xpu-smi.
    Returns a dictionary keyed by GPU identifier (e.g. 'gpu0', 'gpu1') with
    usage details for each GPU.

    Returns:
        dict[str, dict]: Dictionary containing GPU usage metrics for each
            detected GPU. Returns empty dict if no supported GPUs are found
            or the query tools are unavailable.
    """
    gpus = {}
    gpus.update(_get_nvidia_gpu_usage())
    gpus.update(_get_amd_gpu_usage())
    gpus.update(_get_intel_gpu_usage())
    return gpus


def _get_nvidia_gpu_usage() -> dict[str, dict]:
    """Query NVIDIA GPUs using nvidia-smi."""
    nvidia_smi = shutil.which('nvidia-smi')
    if not nvidia_smi:
        return {}

    try:
        result = subprocess.run(
            [
                nvidia_smi,
                '--query-gpu=' + ','.join(NVIDIA_SMI_QUERY_FIELDS),
                '--format=csv,noheader,nounits',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug('Failed to query nvidia-smi: %s', e)
        return {}

    if result.returncode != 0:
        logger.debug('nvidia-smi returned non-zero exit code: %d', result.returncode)
        return {}

    gpus = {}
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < len(NVIDIA_SMI_QUERY_FIELDS):
            continue

        index = parts[0]
        gpu_key = f'gpu{index}'
        gpus[gpu_key] = {
            'index': int(index),
            'name': parts[1],
            'gpu_utilization': _parse_float(parts[2]),
            'memory_utilization': _parse_float(parts[3]),
            'memory_total': _parse_int(parts[4]),
            'memory_used': _parse_int(parts[5]),
            'memory_free': _parse_int(parts[6]),
            'temperature': _parse_int(parts[7]),
            'fan_speed': _parse_int(parts[8]),
            'power_draw': _parse_float(parts[9]),
        }

    return gpus


def _get_amd_gpu_usage() -> dict[str, dict]:
    """Query AMD GPUs using rocm-smi with JSON output."""
    rocm_smi = shutil.which('rocm-smi')
    if not rocm_smi:
        return {}

    try:
        result = subprocess.run(
            [
                rocm_smi,
                '--showuse', '--showmemuse', '--showtemp',
                '--showpower', '--showfan', '--showproductname',
                '--showmeminfo', 'vram',
                '--json',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug('Failed to query rocm-smi: %s', e)
        return {}

    if result.returncode != 0:
        logger.debug('rocm-smi returned non-zero exit code: %d', result.returncode)
        return {}

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug('Failed to parse rocm-smi JSON output: %s', e)
        return {}

    gpus = {}
    for card_index, (card_key, card_data) in enumerate(sorted(data.items())):
        if not card_key.startswith('card'):
            continue

        vram_total_bytes = _parse_int(card_data.get('VRAM Total Memory (B)'))
        vram_used_bytes = _parse_int(card_data.get('VRAM Total Used Memory (B)'))
        vram_total_mib = int(vram_total_bytes / (1024 * 1024)) if vram_total_bytes is not None else None
        vram_used_mib = int(vram_used_bytes / (1024 * 1024)) if vram_used_bytes is not None else None
        vram_free_mib = (vram_total_mib - vram_used_mib) if (
            vram_total_mib is not None and vram_used_mib is not None
        ) else None

        gpu_use = _parse_float(card_data.get('GPU use (%)'))
        mem_use = _parse_float(card_data.get('GPU memory use (%)'))

        temperature = _amd_parse_temperature(card_data)
        power_draw = _amd_parse_power(card_data)

        fan_speed_raw = card_data.get('Fan Speed (%)')
        fan_speed = _parse_int(fan_speed_raw) if fan_speed_raw else None

        name = card_data.get('Card Series') or card_data.get('Card Model') or f'AMD GPU {card_key}'

        gpu_key = f'gpu{card_index}'
        gpus[gpu_key] = {
            'index': card_index,
            'name': name,
            'gpu_utilization': gpu_use,
            'memory_utilization': mem_use,
            'memory_total': vram_total_mib,
            'memory_used': vram_used_mib,
            'memory_free': vram_free_mib,
            'temperature': temperature,
            'fan_speed': fan_speed,
            'power_draw': power_draw,
        }

    return gpus


def _amd_parse_temperature(card_data: dict) -> int | None:
    """Extract temperature from AMD GPU data, trying common key patterns."""
    for key in card_data:
        if 'temperature' in key.lower() and 'edge' in key.lower():
            val = _parse_int(card_data[key])
            if val is not None:
                return val
    for key in card_data:
        if 'temperature' in key.lower() and '(c)' in key.lower():
            val = _parse_int(card_data[key])
            if val is not None:
                return val
    return None


def _amd_parse_power(card_data: dict) -> float | None:
    """Extract power draw from AMD GPU data, trying common key patterns."""
    for key in card_data:
        if 'power' in key.lower() and '(w)' in key.lower():
            return _parse_float(card_data[key])
    return None


def _get_intel_gpu_usage() -> dict[str, dict]:
    """Query Intel GPUs using xpu-smi."""
    xpu_smi = shutil.which('xpu-smi')
    if not xpu_smi:
        return {}

    discovery = _xpu_smi_discover(xpu_smi)

    try:
        result = subprocess.run(
            [
                xpu_smi, 'dump',
                '-d', '-1',
                '-m', XPU_SMI_METRIC_IDS,
                '-n', '1',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug('Failed to query xpu-smi dump: %s', e)
        return {}

    if result.returncode != 0:
        logger.debug('xpu-smi dump returned non-zero exit code: %d', result.returncode)
        return {}

    gpus = {}
    for line in result.stdout.strip().splitlines():
        if line.startswith('Timestamp'):
            continue

        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 6:
            continue

        device_id = parts[1].strip()
        gpu_key = f'gpu{device_id}'
        device_id_int = _parse_int(device_id)
        if device_id_int is None:
            continue

        info: tuple[str, int] | None = discovery.get(device_id_int)

        vram_total_mib = info[1] if info is not None else None
        vram_used_mib = _parse_int(parts[6]) if len(parts) == 7 else None
        vram_free_mib = (vram_total_mib - vram_used_mib) if (
                vram_total_mib is not None and vram_used_mib is not None
        ) else None

        gpus[gpu_key] = {
            'index': device_id_int,
            'name': info[0] if info is not None else f'Intel GPU {device_id}',
            'gpu_utilization': _parse_float(parts[2]),
            'memory_utilization': _parse_float(parts[5]),
            'memory_total': vram_total_mib,
            'memory_used': vram_used_mib,
            'memory_free': vram_free_mib,
            'temperature': _parse_int(parts[4]),
            'fan_speed': None,
            'power_draw': _parse_float(parts[3]),
        }

    return gpus


def _xpu_smi_discover(xpu_smi: str) -> dict[int, tuple[str, int]]:
    """Get Intel GPU device names via xpu-smi discovery --dump."""
    try:
        result = subprocess.run(
            [xpu_smi, 'discovery', '--dump', XPU_SMI_DISCOVERY_IDS],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug('Failed to query xpu-smi discovery: %s', e)
        return {}

    if result.returncode != 0:
        return {}

    gpus = {}
    for line in result.stdout.strip().splitlines():
        if line.startswith('Device'):
            continue

        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 3:
            continue

        device_id = parts[0].strip()
        device_name = parts[1].replace('"', '')
        memory_total_mb = _parse_int(parts[2].replace('"', '').replace(' MiB', ''))
        device_id_int = _parse_int(device_id)
        if device_id_int is None:
            continue

        gpus[device_id_int] = (device_name, memory_total_mb)

    return gpus


def _parse_float(value: str) -> float | None:
    """Parse a float value, returning None for unavailable readings."""
    try:
        return round(float(value), 2)
    except (ValueError, TypeError):
        return None


def _parse_int(value: str) -> int | None:
    """Parse an integer value, returning None for unavailable readings."""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None
