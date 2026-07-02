import collections
import functools
import os
import re
import typing
from typing import Any

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
# coretemp per-core label ('Core N', N == package-relative core_id) and the
# package label ('Package id N', N == physical_package_id used for chip->package
# resolution); k10temp per-CCD label ('Tccd<N>', N-1 == die_id).
RE_CORE = re.compile(r'^Core ([0-9]+)$')
RE_PACKAGE = re.compile(r'^Package id ([0-9]+)$')
RE_TCCD = re.compile(r'Tccd(\d+)')

sensors = None


class CpuInfo(typing.TypedDict):
    cpu_model: str | None
    """The CPU model"""
    core_count: int | None
    """The total number of online logical CPUs"""
    physical_core_count: int
    """The total number of physical CPU cores"""
    logical_to_phys: dict[int, int]
    """Every online logical CPU id -> its physical-core ordinal
       (0..physical_core_count-1)."""
    phys_to_package: dict[int, int]
    """Physical-core ordinal -> physical_package_id (socket index)."""
    phys_to_die: dict[int, int]
    """Physical-core ordinal -> die_id within its package.
       On AMD Zen this is the CCD index. On Intel/most ARM, always 0."""
    phys_to_core_id: dict[int, int]
    """Physical-core ordinal -> core_id within its package
       (used to match Intel coretemp 'Core N' labels to physical cores)."""


CpuFlags = list[str]


def _read_int(path: str) -> int | None:
    """Read a single int from a sysfs file, returning None on missing or
    unparseable content."""
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def _read_str(path: str) -> str | None:
    """Read a sysfs file as text, returning None on missing or unreadable."""
    try:
        with open(path) as f:
            return f.read().strip()
    except (FileNotFoundError, OSError):
        return None


def _parse_cpulist(s: str) -> list[int]:
    """Parse a Linux cpulist format string into the explicit list of CPU IDs.

    Supports comma-separated values, ranges (``"0-3"``), and combinations
    (``"0,2-3"``). Returns an empty list for empty input. Raises ``ValueError``
    on malformed tokens.
    """
    out: list[int] = []
    for part in s.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            lo, hi = part.split('-', 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def _numeric(d: dict[str, Any], key: str) -> float | None:
    """Return ``d[key]`` if it's a numeric reading, else None.

    Uses ``isinstance`` rather than truthiness so a legitimate ``0.0``
    sensor reading is preserved.
    """
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def _read_cpu_model(proc_cpuinfo: str) -> str | None:
    try:
        with open(proc_cpuinfo, 'rb') as f:
            for line in filter(lambda x: x.startswith(b'model name'), f):
                return line.split(b':', 1)[-1].strip().decode() or None
    except (FileNotFoundError, OSError):
        return None
    return None


@functools.cache
def cpu_info() -> CpuInfo:
    return cpu_info_impl()


def cpu_info_impl(
    sys_cpu_root: str = '/sys/devices/system/cpu/',
    proc_cpuinfo: str = '/proc/cpuinfo',
) -> CpuInfo:
    """Build the topology snapshot for the temperature pipeline.

    Walks ``<sys_cpu_root>/cpuN/topology/`` once and reads ``proc_cpuinfo``
    for the model name. Each physical core gets a stable ordinal
    (0..N-1) keyed by its lowest online logical CPU id, and four maps are
    produced (``logical_to_phys``, ``phys_to_package``, ``phys_to_die``,
    ``phys_to_core_id``) so a reading can be attributed to a physical core
    and then projected onto every logical CPU that shares it.

    The roots are parameters so unit tests can point at a fake sysfs tree.
    """
    cc = os.sysconf('SC_NPROCESSORS_ONLN') or None
    cm = _read_cpu_model(proc_cpuinfo)

    # core_cpus_list is in Linux cpulist format; examples:
    #   "0,8" - HT pair the kernel enumerates non-consecutively
    #   "0-1" - HT pair the kernel enumerates consecutively
    #   "0"   - SMT disabled (only the primary thread is online)
    #   "0-3" - 4-way SMT (POWER) or wider
    core_meta: dict[int, tuple[list[int], int, int, int]] = {}
    with os.scandir(sys_cpu_root) as sdir:
        for entry in filter(lambda x: x.is_dir() and x.name.startswith('cpu'), sdir):
            try:
                int(entry.name[len('cpu'):])
            except ValueError:
                # Skip non-numeric subdirs (cpufreq, cpuidle, etc.).
                continue
            topo = os.path.join(entry.path, 'topology')
            siblings_str = _read_str(os.path.join(topo, 'core_cpus_list'))
            if siblings_str is None:
                continue
            try:
                siblings = _parse_cpulist(siblings_str)
            except ValueError:
                continue
            if not siblings:
                continue
            # The lowest logical CPU id is unique per physical core (sibling
            # sets are disjoint) and is also the stable ordinal sort key.
            core_key = min(siblings)
            if core_key in core_meta:
                continue  # already recorded via another sibling cpuN dir
            pkg = _read_int(os.path.join(topo, 'physical_package_id'))
            die = _read_int(os.path.join(topo, 'die_id'))
            cid = _read_int(os.path.join(topo, 'core_id'))
            core_meta[core_key] = (
                siblings,
                pkg if pkg is not None and pkg >= 0 else 0,
                die if die is not None and die >= 0 else 0,
                cid if cid is not None and cid >= 0 else 0,
            )

    logical_to_phys: dict[int, int] = {}
    phys_to_package: dict[int, int] = {}
    phys_to_die: dict[int, int] = {}
    phys_to_core_id: dict[int, int] = {}
    for phys_idx, core_key in enumerate(sorted(core_meta.keys())):
        siblings, pkg, die, cid = core_meta[core_key]
        for cpu_id in sorted(siblings):
            logical_to_phys[cpu_id] = phys_idx
        phys_to_package[phys_idx] = pkg
        phys_to_die[phys_idx] = die
        phys_to_core_id[phys_idx] = cid

    return CpuInfo(
        cpu_model=cm,
        core_count=cc,
        physical_core_count=len(core_meta),
        logical_to_phys=logical_to_phys,
        phys_to_package=phys_to_package,
        phys_to_die=phys_to_die,
        phys_to_core_id=phys_to_core_id,
    )


def _phys_indexes(
    cinfo: CpuInfo,
) -> tuple[dict[int, list[int]], dict[tuple[int, int], list[int]], dict[int, dict[int, int]]]:
    """Flip the CpuInfo maps into the lookups the attribution routines want:
      - pkg_to_phys:      package_id -> physical-core ordinals in that package
      - pkg_die_to_phys:  (package_id, die_id) -> physical-core ordinals (AMD)
      - pkg_core_to_phys: package_id -> {core_id: phys_idx} (Intel 'Core N')
    Not cached: it is derived from the passed-in snapshot so tests that patch
    cpu_info aren't frozen by a module-level cache.
    """
    pkg_to_phys: dict[int, list[int]] = collections.defaultdict(list)
    pkg_die_to_phys: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    pkg_core_to_phys: dict[int, dict[int, int]] = collections.defaultdict(dict)
    for phys, pkg in cinfo['phys_to_package'].items():
        pkg_to_phys[pkg].append(phys)
        pkg_die_to_phys[(pkg, cinfo['phys_to_die'][phys])].append(phys)
        pkg_core_to_phys[pkg][cinfo['phys_to_core_id'][phys]] = phys
    return (
        dict(pkg_to_phys),
        dict(pkg_die_to_phys),
        {k: dict(v) for k, v in pkg_core_to_phys.items()},
    )


def _chip_family(chip_name: str) -> str:
    """The driver family of a libsensors chip name, e.g. 'coretemp-isa-0000'
    -> 'coretemp', 'k10temp-pci-00c3' -> 'k10temp'."""
    return chip_name.split('-', 1)[0]


def _resolve_packages(chips: dict[str, Any]) -> dict[str, int]:
    """Resolve which physical_package_id each CPU thermal chip serves.

    Multi-socket boxes expose several chips of the same family (two
    ``coretemp-isa-*`` on dual-Xeon, two ``k10temp-pci-*`` on dual-EPYC), and
    each chip's ``Core 0`` is a different physical core, so per-chip package
    resolution is required to avoid mis-attribution.

    - coretemp: prefer the chip's own ``Package id N`` label (kernel-emitted),
      then the ISA-suffix hex, then an alphabetical per-family index.
    - k10temp/k8temp: alphabetical per-family index. libsensors does not carry
      the PCI ``numa_node`` used for kernel-truth resolution, so this is the
      fallback path (single-socket always resolves to 0; a dual-socket box
      relies on PCI-address ordering tracking the socket order).
    - via_cputemp/cpu_thermal (ARM/generic): package 0.
    """
    type_index: dict[str, int] = collections.defaultdict(int)
    out: dict[str, int] = {}
    for chip_name in sorted(chips):
        fam = _chip_family(chip_name)
        idx = type_index[fam]
        type_index[fam] += 1
        if fam == 'coretemp':
            pkg = None
            for label in chips[chip_name]:
                if m := RE_PACKAGE.match(label):
                    pkg = int(m.group(1))
                    break
            if pkg is None:
                try:
                    pkg = int(chip_name.rsplit('-', 1)[-1], 16)
                except ValueError:
                    pkg = idx
            out[chip_name] = pkg
        elif fam in AMD_PREFIXES:
            out[chip_name] = idx
        else:
            out[chip_name] = 0
    return out


def _intel_assignments(
    chip_data: dict[str, Any],
    pkg_core_index: dict[int, int],
) -> dict[int, float]:
    """Map an Intel coretemp chip's 'Core N' labels onto physical-core ordinals.

    ``N`` is the package-relative ``core_id``, resolved to a physical-core
    ordinal via ``pkg_core_index`` (the slice of ``pkg_core_to_phys`` for this
    chip's package). The ``Package id N`` label is ignored here (it drives
    chip-to-package resolution). Cores with a broken/missing DTS simply don't
    appear in ``chip_data`` and are omitted.
    """
    out: dict[int, float] = {}
    for label, val in chip_data.items():
        m = RE_CORE.match(label)
        if m is None:
            continue
        phys = pkg_core_index.get(int(m.group(1)))
        if phys is not None:
            out[phys] = val
    return out


def _amd_assignments(
    chip_data: dict[str, Any],
    chip_pkg: int,
    cpu_model: str | None,
    pkg_to_phys: dict[int, list[int]],
    pkg_die_to_phys: dict[tuple[int, int], list[int]],
) -> dict[int, float]:
    """Map a k10temp/k8temp chip's labels onto physical-core ordinals.

    1. AMD_PREFER_TDIE models with Tdie present -> Tdie for every core in the
       package (sidesteps Tctl's fan-control offset; Tccd skipped).
    2. Otherwise each ``Tccd<N>`` is assigned to the cores whose ``die_id ==
       N - 1`` within the package.
    3. Any core not covered by a Tccd falls back to the first available of
       Tdie / Tctl / temp1. Zero readings are preserved.
    """
    out: dict[int, float] = {}

    tdie = _numeric(chip_data, 'Tdie')
    tctl = _numeric(chip_data, 'Tctl')
    temp1 = _numeric(chip_data, 'temp1')
    prefer_tdie = cpu_model is not None and cpu_model.startswith(AMD_PREFER_TDIE) and tdie is not None

    # Step 1: per-CCD assignments (skipped on AMD_PREFER_TDIE + Tdie).
    # Tccd<N> corresponds to kernel die_id == N - 1 (same firmware slot order).
    if not prefer_tdie:
        for label, val in chip_data.items():
            m = RE_TCCD.fullmatch(label)
            if m is None:
                continue
            ccd_idx = int(m.group(1)) - 1
            for phys in pkg_die_to_phys.get((chip_pkg, ccd_idx), ()):
                out[phys] = val

    # Step 2: package-wide fallback for cores without a Tccd assignment.
    if prefer_tdie:
        package_temp: float | None = tdie
    else:
        package_temp = next((t for t in (tdie, tctl, temp1) if t is not None), None)
    if package_temp is not None:
        for phys in pkg_to_phys.get(chip_pkg, ()):
            out.setdefault(phys, package_temp)

    return out


def _generic_single_temp_assignments(
    chip_data: dict[str, Any],
    chip_pkg: int,
    pkg_to_phys: dict[int, list[int]],
) -> dict[int, float]:
    """via_cputemp / cpu_thermal: a single-temp chip; broadcast temp1 across
    every physical core in the chip's package."""
    out: dict[int, float] = {}
    t = _numeric(chip_data, 'temp1')
    if t is None:
        return out
    for phys in pkg_to_phys.get(chip_pkg, ()):
        out.setdefault(phys, t)
    return out


def read_cpu_temps() -> dict[str, Any]:
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


def get_cpu_temperatures() -> dict[str, float]:
    """Produce the per-logical-CPU temperature snapshot for the dashboard.

    Return shape (one entry per online logical CPU plus an aggregate)::

        {'cpu0': float, ..., 'cpu<core_count-1>': float, 'cpu': float}

    Each chip's readings are attributed to physical cores (Intel by
    ``core_id``, AMD by ``die_id`` with a package fallback, generic by
    package broadcast), projected onto every logical CPU sharing that core,
    and the aggregate ``cpu`` is the mean across physical cores -- so
    asymmetric SMT does not bias it. When no sensors are readable, every
    value is ``0.0`` so consumers keep their chart dimensions.
    """
    cinfo = cpu_info()
    chips = read_cpu_temps()
    pkg_to_phys, pkg_die_to_phys, pkg_core_to_phys = _phys_indexes(cinfo)
    chip_pkg = _resolve_packages(chips)

    phys_temps: dict[int, float] = {}
    for chip_name, chip_data in chips.items():
        if not chip_data:
            continue
        fam = _chip_family(chip_name)
        pkg = chip_pkg[chip_name]
        if fam in AMD_PREFIXES:
            phys_temps.update(
                _amd_assignments(chip_data, pkg, cinfo['cpu_model'], pkg_to_phys, pkg_die_to_phys)
            )
        elif fam == 'coretemp':
            phys_temps.update(_intel_assignments(chip_data, pkg_core_to_phys.get(pkg, {})))
        else:
            phys_temps.update(_generic_single_temp_assignments(chip_data, pkg, pkg_to_phys))

    data: dict[str, float] = {}
    for logical_id, phys in cinfo['logical_to_phys'].items():
        t = phys_temps.get(phys)
        if t is not None:
            data[f'cpu{logical_id}'] = t

    if data and phys_temps:
        data['cpu'] = sum(phys_temps.values()) / len(phys_temps)
        return data

    return {f'cpu{i}': 0.0 for i in range(cinfo['core_count'] or 0)} | {'cpu': 0.0}


@functools.cache
def cpu_flags() -> CpuFlags:
    with open('/proc/cpuinfo', 'rb') as f:
        for line in filter(lambda x: x.startswith((b'processor', b'flags')), f):
            parts = line.decode('utf-8').split(':', 1)
            title = parts[0].strip()
            if title == 'flags':
                return parts[1].strip().split()
    return []
