import functools
import json
import psutil
import re
import subprocess

from collections import defaultdict


AMD_PREFER_TDIE = (
    # https://github.com/torvalds/linux/blob/master/drivers/hwmon/k10temp.c#L121
    # static const struct tctl_offset tctl_offset_table[] = {
    'AMD Ryzen 5 1600X',
    'AMD Ryzen 7 1700X',
    'AMD Ryzen 7 1800X',
    'AMD Ryzen 7 2700X',
    'AMD Ryzen Threadripper 19',
    'AMD Ryzen Threadripper 29',
)
RE_CORE = re.compile(r'^Core ([0-9]+)$')
RE_CPU_MODEL = re.compile(r'^model name\s*:\s*(.*)', flags=re.M)


@functools.cache
def cpu_info() -> dict:
    return {
        'cpu_model': get_cpu_model(),
        'core_count': psutil.cpu_count(logical=True),
        'physical_core_count': psutil.cpu_count(logical=False),
    }


def get_cpu_model():
    with open('/proc/cpuinfo', 'r') as f:
        model = RE_CPU_MODEL.search(f.read())
        return model.group(1) if model else None


def cpu_temperatures() -> dict:
    cp = subprocess.run(['sensors', '-j'], capture_output=True, text=True)
    sensors = json.loads(cp.stdout)
    amd_sensor = sensors.get('k10temp-pci-00c3')
    if amd_sensor:
        data = _amd_cpu_temperatures(amd_sensor)
    else:
        data = _generic_cpu_temperatures(sensors)

    return {str(k): v for k, v in data.items()}


def _generic_cpu_temperatures(sensors: dict) -> dict:
    temperatures = defaultdict(dict)
    for chip, value in sensors.items():
        for name, temps in value.items():
            if not (m := RE_CORE.match(name)):
                continue
            for temp, value in temps.items():
                if 'input' in temp:
                    temperatures[chip][int(m.group(1))] = value
                    break

    return dict(enumerate(sum(
        [
            [temperatures[chip][core] for core in sorted(temperatures[chip].keys())]
            for chip in sorted(temperatures.keys())
        ],
        [],
    )))


def _amd_cpu_temperatures(amd_sensor: dict) -> dict:
    cpu_model = cpu_info()['cpu_model']
    core_count = cpu_info()['physical_core_count']

    ccds = []
    for k, v in amd_sensor.items():
        if k.startswith('Tccd') and v:
            t = list(v.values())[0]
            if isinstance(t, (int, float)):
                ccds.append(t)
    has_tdie = (
        'Tdie' in amd_sensor and amd_sensor['Tdie'] and isinstance(list(amd_sensor['Tdie'].values())[0], (int, float))
    )
    if cpu_model.startswith(AMD_PREFER_TDIE) and has_tdie:
        return _amd_cpu_tdie_temperatures(amd_sensor, core_count)
    elif ccds and core_count % len(ccds) == 0:
        return dict(enumerate(sum([[t] * (core_count // len(ccds)) for t in ccds], [])))
    elif has_tdie:
        return _amd_cpu_tdie_temperatures(amd_sensor, core_count)
    elif (
        'Tctl' in amd_sensor and amd_sensor['Tctl'] and isinstance(list(amd_sensor['Tctl'].values())[0], (int, float))
    ):
        return dict(enumerate([list(amd_sensor['Tctl'].values())[0]] * core_count))
    elif 'temp1' in amd_sensor and 'temp1_input' in amd_sensor['temp1']:
        return dict(enumerate([amd_sensor['temp1']['temp1_input']] * core_count))


def _amd_cpu_tdie_temperatures(amd_sensor: dict, core_count: int) -> dict:
    return dict(enumerate([list(amd_sensor['Tdie'].values())[0]] * core_count))
