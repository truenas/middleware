import collections
import functools
import os
import re
import typing


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
    elif 'temp1' in amd_sensors:
        if isinstance(amd_sensors['temp1'], float):
            return dict(enumerate([amd_sensors['temp1']] * core_count))
        elif 'temp1_input' in amd_sensors['temp1']:
            return dict(enumerate([amd_sensors['temp1']['temp1_input']] * core_count))
