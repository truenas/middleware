import collections
import functools
import os
import re
import typing

from middlewared.utils.sensors import SensorsWrapper


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
AMD_PREFIXES = (
    'k8temp',
    'k10temp',
)
RE_CORE = re.compile(r'^Core ([0-9]+)$')

sensors = None


class CpuInfo(typing.TypedDict):
    cpu_model: str | None
    """The CPU model"""
    core_count: int
    """The total number of online CPUs"""
    physical_core_count: int
    """The total number of physical CPU cores"""
    ht_map: dict[str, str]
    """A mapping of physical core ids to their
        hyper-threaded ids
        (i.e. {"cpu0": "cpu8", "cpu1": "cpu9"})"""


CpuFlags = list[str]


@functools.cache
def cpu_info() -> CpuInfo:
    return cpu_info_impl()


def cpu_info_impl() -> CpuInfo:
    cc = os.sysconf('SC_NPROCESSORS_ONLN') or None

    cm = None
    with open('/proc/cpuinfo', 'rb') as f:
        for line in filter(lambda x: x.startswith(b'model name'), f):
            cm = line.split(b':')[-1].strip().decode() or None
            break

    pcc = set()
    ht_map = dict()
    with os.scandir('/sys/devices/system/cpu/') as sdir:
        for i in filter(lambda x: x.is_dir() and x.name.startswith('cpu'), sdir):
            try:
                with open(os.path.join(i.path, 'topology/core_cpus_list')) as f:
                    _pcc = f.read().strip()
                    pcc.add(_pcc)
                    pcid, htid = '', ''
                    for sep in (',', '-'):
                        # file is written with commas or hyphens
                        try:
                            pcid, htid = _pcc.split(sep)
                        except ValueError:
                            continue

                    if i.name[len('cpu'):] == htid:
                        # the directory we're in is named `cpu0/1/2/etc`
                        # and if the 1st number in the cores_cpus_list
                        # file is the same as the directory, then it's
                        # a physical core. Otherwise, it's a HT core.
                        # Hyper-Threaded Example:
                        #   directory name == cpu8
                        #   file contents == 0,8
                        #   This means `cpu8` is a hyper-threaded core
                        #   because the `8` in `cpu8` doesn't match the
                        #   first number in the file (0,8)
                        # Physical Core Example:
                        #   directory name == cpu0
                        #   file contents == 0,8
                        #   This means `cpu0` is a physical core because
                        #   the `0` in `cpu0` matches the first number
                        #   in the file (0,8)
                        ht_map[f'cpu{pcid}'] = i.name
            except FileNotFoundError:
                continue

    return CpuInfo(
        cpu_model=cm,
        core_count=cc,
        physical_core_count=len(pcc),
        ht_map=ht_map,
    )


def generic_cpu_temperatures(cpu_metrics: dict) -> dict:
    temperatures = collections.defaultdict(dict)
    for chip_name in filter(lambda sen: sen.startswith('coretemp'), cpu_metrics):
        for label, temp in cpu_metrics[chip_name].items():
            if not (m := RE_CORE.match(label)):
                continue
            temperatures[chip_name][int(m.group(1))] = temp

    return dict(enumerate(sum(
        [
            [temperatures[chip][core] for core in sorted(temperatures[chip].keys())]
            for chip in sorted(temperatures.keys())
        ],
        [],
    )))


def amd_cpu_temperatures(amd_sensors: dict) -> dict:
    cpu_model = cpu_info()['cpu_model']
    core_count = cpu_info()['physical_core_count']

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
    elif 'temp1' in amd_sensors:
        if isinstance(amd_sensors['temp1'], float):
            return dict(enumerate([amd_sensors['temp1']] * core_count))
        elif 'temp1_input' in amd_sensors['temp1']:
            return dict(enumerate([amd_sensors['temp1']['temp1_input']] * core_count))


def read_cpu_temps() -> dict:
    """
    Read CPU temperatures using libsensors.
    Returns data in the format expected by existing temperature processing functions.

    Returns:
        Dictionary with chip names as keys and temperature readings as nested dicts
        Example: {'coretemp-isa-0000': {'Core 0': 48.0}, 'k10temp-pci-00c3': {'Tctl': 67.0}}
    """
    global sensors
    if sensors is None:
        try:
            sensors = SensorsWrapper()
            sensors.init()
        except (OSError, RuntimeError):
            return {}

    try:
        return sensors.get_cpu_temperatures()
    except (OSError, RuntimeError):
        sensors = None
        return {}


def get_cpu_temperatures() -> dict:
    chips = read_cpu_temps()
    amd_sensors = {}
    for key, vals in chips.items():
        if isinstance(vals, dict) and key.startswith(AMD_PREFIXES):
            amd_sensors.update(vals)

    if amd_sensors:
        cpu_data = amd_cpu_temperatures(amd_sensors) or {}
    else:
        cpu_data = generic_cpu_temperatures(chips) or {}

    data = {}
    total_temp = 0
    cinfo = cpu_info()
    for core, temp in cpu_data.items():
        data[f'cpu{core}'] = temp
        total_temp += temp
        try:
            # we follow the paradigm that htop uses
            # for filling in the hyper-threaded ids
            # temperatures. (i.e. we just copy the
            # temp of the parent physical core id)
            data[cinfo['ht_map'][f'cpu{core}']] = temp
            total_temp += temp
        except KeyError:
            continue

    if total_temp:
        data['cpu'] = total_temp / len(data)

    return data or ({f'cpu{i}': 0 for i in range(cinfo['core_count'])} | {'cpu': 0})


@functools.cache
def cpu_flags() -> dict[int, CpuFlags]:
    result = {}
    with open('/proc/cpuinfo', 'rb') as f:
        for line in filter(lambda x: x.startswith((b'processor', b'flags')), f):
            parts = line.decode('utf-8').split(':', 1)
            title = parts[0].strip()
            match title:
                case 'processor':
                    cpu_number = int(parts[1].strip())
                case 'flags':
                    result[cpu_number] = parts[1].strip().split()
        return result
