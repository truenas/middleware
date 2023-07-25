import functools
import psutil
import re

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


def generic_cpu_temperatures(cpu_metrics: dict) -> dict:
    temperatures = defaultdict(dict)
    for chip_name in filter(lambda sen: sen.startswith('coretemp-isa'), cpu_metrics):
        for temp in cpu_metrics[chip_name].values():
            if not (m := RE_CORE.match(temp['name'])):
                continue
            temperatures[chip_name][int(m.group(1))] = temp['value']

    return dict(enumerate(sum(
        [
            [temperatures[chip][core] for core in sorted(temperatures[chip].keys())]
            for chip in sorted(temperatures.keys())
        ],
        [],
    )))


def amd_cpu_temperatures(amd_metrics: dict) -> dict:
    cpu_model = cpu_info()['cpu_model']
    core_count = cpu_info()['physical_core_count']
    amd_sensors = {}
    for amd_sensor in amd_metrics.values():
        amd_sensors[amd_sensor['name']] = amd_sensor['value']

    ccds = []
    for k, v in amd_sensors.items():
        if k.startswith('Tccd') and v:
            if isinstance(v, (int, float)):
                ccds.append(v)
    has_tdie = (
        'Tdie' in amd_sensors and amd_sensors['Tdie'] and isinstance(amd_sensors['Tdie'], (int, float))
    )
    if cpu_model.startswith(AMD_PREFER_TDIE) and has_tdie:
        return dict(enumerate([amd_sensors['Tdie']] * core_count))
    elif ccds and core_count % len(ccds) == 0:
        return dict(enumerate(sum([[t] * (core_count // len(ccds)) for t in ccds], [])))
    elif has_tdie:
        return dict(enumerate([amd_sensors['Tdie']] * core_count))
    elif (
        'Tctl' in amd_sensors and amd_sensors['Tctl'] and isinstance(amd_sensors['Tctl'], (int, float))
    ):
        return dict(enumerate([amd_sensors['Tctl']] * core_count))
    elif 'temp1' in amd_sensors and 'temp1_input' in amd_sensors['temp1']:
        return dict(enumerate([amd_sensors['temp1']['temp1_input']] * core_count))
