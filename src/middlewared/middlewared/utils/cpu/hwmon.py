"""``/sys/class/hwmon`` chip discovery and per-call temperature reading.

Discovery is cached for the process lifetime: hwmon device numbering is
fixed at boot. Per-label ``tempN_input`` paths are resolved once at
discovery time and stored on each ``_Chip`` so the hot path only does the
actual file read.

Chip-to-package resolution:
  - coretemp: prefer the chip's own ``"Package id N"`` label
    (kernel-emitted, unambiguous). Fallback to the platform device's
    ``coretemp.M`` suffix, then to the alphabetical fallback index.
  - k10temp / k8temp: read ``device/numa_node`` and cross-reference the
    kernel's NUMA topology via ``_numa_to_pkg()``. If ``numa_node == -1``
    (BIOS quirk, single socket), fall back to the alphabetical index.
  - via_cputemp / cpu_thermal: package 0 (single-socket assumption).
"""

import collections
from dataclasses import dataclass
import functools
import logging
import os
import re

from ._helpers import _parse_cpulist, _read_int, _read_str
from .info import cpu_info

logger = logging.getLogger(__name__)

CPU_HWMON_NAMES = ("coretemp", "k10temp", "k8temp", "via_cputemp", "cpu_thermal")
MILLIDEG = 1000.0

# coretemp emits a "Package id N" label per package; we use it during
# chip-to-package resolution. (RE_CORE for per-core Intel labels lives in
# intel.py with the assignment logic.)
RE_PACKAGE = re.compile(r"^Package id ([0-9]+)$")


@dataclass(slots=True, frozen=True, kw_only=True)
class _Chip:
    """Cached metadata for one /sys/class/hwmon/hwmonN entry that exposes a
    CPU thermal driver. Stable for the process lifetime."""

    hwmon_path: str
    name: str  # e.g. 'k10temp', 'coretemp'
    package_id: int  # physical_package_id this chip serves
    label_to_input: tuple[tuple[str, str], ...]
    """(label, tempN_input path) pairs, resolved at discovery time."""


@functools.cache
def _numa_to_pkg() -> dict[int, int]:
    """Build a ``numa_node -> physical_package_id`` map once per process.

    What NUMA is and why we need it here
    ------------------------------------
    NUMA (Non-Uniform Memory Access) groups CPUs and memory into
    "nodes" so the kernel can keep workloads on the cores closest to
    their RAM. On nearly every modern AMD/Intel server, each socket
    is one NUMA node, so the NUMA node id is effectively a synonym
    for the socket index. The kernel exposes one directory per node
    at ``/sys/devices/system/node/nodeN/`` with a ``cpulist`` file
    listing the CPUs that live on that node.

    Why this map exists: AMD's ``k10temp`` driver attaches to a PCI
    device, and that PCI device's ``numa_node`` attribute tells us
    which NUMA node the chip serves. To convert that into a
    ``physical_package_id`` (the field we actually attribute
    temperatures by) we need to look up "what package is this NUMA
    node?". This function pre-computes that lookup so every
    ``k10temp-pci-*`` chip resolution is O(1) instead of an
    on-demand sysfs walk.

    Behavior on edge cases
    ----------------------
    - No NUMA support exposed (``/sys/devices/system/node/`` missing)
      -> empty map; callers fall back to alphabetical chip-name index.
    - ``numa_node == -1`` on the chip -> map lookup misses; same
      fallback. Common on single-socket boxes where NUMA topology
      isn't exposed by firmware.
    - Multi-NUMA-per-socket (rare; some AMD EPYC NPS4 modes) -> we
      pick one package id per node, which is technically right since
      every CPU in a NUMA node still shares a single
      ``physical_package_id``.
    """
    cinfo = cpu_info()
    out: dict[int, int] = {}
    node_root = "/sys/devices/system/node"
    try:
        with os.scandir(node_root) as entries:
            for entry in entries:
                if not (entry.is_dir() and entry.name.startswith("node")):
                    continue
                try:
                    node_id = int(entry.name[len("node") :])
                except ValueError:
                    continue
                cpulist = _read_str(os.path.join(entry.path, "cpulist"))
                if not cpulist:
                    continue
                try:
                    cpus = _parse_cpulist(cpulist)
                except ValueError:
                    continue
                for cpu_id in cpus:
                    phys = cinfo["logical_to_phys"].get(cpu_id)
                    if phys is not None:
                        out[node_id] = cinfo["phys_to_package"][phys]
                        break
    except OSError:
        return out
    return out


def _resolve_chip_package(
    hwmon_path: str,
    chip_name: str,
    labels: dict[str, str],
    fallback_index: int,
) -> int:
    """Resolve which ``physical_package_id`` a CPU thermal chip serves.

    Multi-socket boxes have multiple chips of the same kind (two
    ``coretemp-isa-*`` entries on dual-Xeon, two ``k10temp-pci-*``
    entries on dual-EPYC, etc.). Each chip's ``"Core 0"`` is a
    different physical core, so without per-chip package resolution
    readings get silently mis-attributed.

    Resolution strategy per chip family
    -----------------------------------
    - **coretemp (Intel)** -- the kernel emits a ``"Package id N"``
      label on every coretemp chip; ``N`` is the
      ``physical_package_id``. We trust that label first because it
      comes straight from the kernel. If the chip somehow lacks the
      label, we fall back to the platform device's name suffix
      (``/sys/devices/platform/coretemp.M`` -> ``M``), then to the
      caller-provided alphabetical ``fallback_index``.
    - **k10temp / k8temp (AMD)** -- there's no per-package label, but
      the chip is a PCI device whose ``numa_node`` attribute names the
      NUMA node it serves. We cross-reference that against
      :func:`_numa_to_pkg` to recover ``physical_package_id``. If
      ``numa_node`` is missing or ``-1`` (BIOS quirk; common on
      single-socket boxes that don't bother exposing NUMA) we fall
      back to ``fallback_index`` and log a warning.
    - **via_cputemp / cpu_thermal** -- always package 0. These appear
      on single-socket VIA / ARM hardware where multi-package
      attribution is meaningless.

    The ``fallback_index`` is a per-chip-type counter assigned in
    alphabetical chip-name order by :func:`_discover_cpu_chips`. So
    when the kernel-truth path fails, we degrade to the same
    "alphabetical chip name == package index" hypothesis that htop
    and lm-sensors users implicitly rely on -- but only as a last
    resort, with a warning to make it visible.
    """
    if chip_name == "coretemp":
        # ``labels`` is {label_string: tempN_input path} -- iterate the keys
        # to match the kernel-emitted "Package id N" label.
        for label in labels:
            m = RE_PACKAGE.match(label)
            if m is not None:
                return int(m.group(1))
        device_path = os.path.realpath(os.path.join(hwmon_path, "device"))
        base = os.path.basename(device_path)
        if base.startswith("coretemp."):
            try:
                return int(base[len("coretemp.") :])
            except ValueError:
                pass
        return fallback_index

    if chip_name in ("k10temp", "k8temp"):
        nn = _read_int(os.path.join(hwmon_path, "device", "numa_node"))
        if nn is not None and nn >= 0:
            pkg = _numa_to_pkg().get(nn)
            if pkg is not None:
                return pkg
        # Single-socket boxes commonly report numa_node == -1; fall back to
        # the alphabetical-chip-name index. With one chip this is always 0.
        if nn is None or nn < 0:
            logger.debug(
                "%s: numa_node missing/-1; using alphabetical chip-name "
                "index %d as physical_package_id (hypothesis fallback)",
                hwmon_path,
                fallback_index,
            )
        return fallback_index

    return 0


@functools.cache
def _discover_cpu_chips() -> tuple[_Chip, ...]:
    """Enumerate CPU thermal chips once per process.

    What hwmon is
    -------------
    ``/sys/class/hwmon/`` is the kernel's hardware-monitoring
    interface. Every driver that reports temperatures (CPU, NVMe,
    motherboard, GPU, ...) registers a ``hwmon`` device that shows up
    as ``/sys/class/hwmon/hwmonN/``. Inside each one:

    - ``name``                 -- the driver name (``coretemp``,
      ``k10temp``, ``nvme``, ...).
    - ``tempN_input``          -- the live temperature reading for
      sensor N, in **millidegrees Celsius** (so ``50000`` means
      50.0 C). This is what we read on every call to
      :func:`get_cpu_temperatures`.
    - ``tempN_label``          -- the human label for sensor N
      (``"Core 0"``, ``"Tctl"``, ``"Tccd1"``, ...). The label is the
      driver's promise about what the reading means; it's how we
      know which physical core / die / package to attribute it to.
    - ``device``               -- a symlink to the underlying device
      (PCI device for ``k10temp``, platform device for ``coretemp``).
      Walked during package resolution.

    What this function does
    -----------------------
    1. Filter ``/sys/class/hwmon/`` down to chips whose ``name``
       starts with one of :data:`CPU_HWMON_NAMES` (everything else is
       drives, GPUs, fan controllers -- not our concern).
    2. Build a ``label -> tempN_input path`` map for each chip by
       reading every ``tempN_label`` file and pairing it with the
       matching ``tempN_input`` path. The pair is stored on the
       :class:`_Chip` so the hot path never re-reads label files.
    3. Handle drivers that omit labels (some old k8temp builds): use
       ``"tempN"`` as the synthetic label so the legacy temp1 fallback
       in :func:`amd._amd_assignments` keeps working.
    4. Assign each chip a ``package_id`` via
       :func:`_resolve_chip_package`.

    Why caching is safe
    -------------------
    hwmon device numbering is fixed at boot: drivers load in a
    deterministic order and ``hwmonN`` numbers stick around for the
    process's life. Topology doesn't shift either (see
    :func:`info.cpu_info` for the same reasoning). So we cache once
    per process and the hot path is reduced to "for each cached chip,
    open its tempN_input files".

    The escape hatch for an unloaded/reloaded driver is the same as
    today: :func:`_read_chip_temps` returns an empty dict if any
    file vanished, and the aggregate falls through to its
    all-zero default.
    """
    hwmon_root = "/sys/class/hwmon"
    try:
        with os.scandir(hwmon_root) as it:
            entries = sorted(it, key=lambda e: e.name)
    except OSError:
        return ()

    temp_len = len("temp")
    label_suffix_len = len("_label")
    input_suffix_len = len("_input")

    candidates: list[tuple[str, str, dict[str, str]]] = []
    for entry in entries:
        if not entry.name.startswith("hwmon"):
            continue
        name = _read_str(os.path.join(entry.path, "name"))
        if not name or not name.startswith(CPU_HWMON_NAMES):
            continue
        # Build label -> tempN_input map once.
        labels: dict[str, str] = {}
        try:
            with os.scandir(entry.path) as files_it:
                files = [f.name for f in files_it]
        except OSError:
            continue
        for fname in files:
            if not fname.startswith("temp"):
                continue
            if not fname.endswith("_label"):
                continue
            n = fname[temp_len:-label_suffix_len]
            if not n.isdigit():
                continue
            label = _read_str(os.path.join(entry.path, fname))
            if not label:
                # Some chips expose a tempN_input without a tempN_label; the
                # convention is to fall back to "tempN" as the label so the
                # legacy temp1 branch (k8temp) keeps working.
                label = f"temp{n}"
            input_path = os.path.join(entry.path, f"temp{n}_input")
            if os.path.exists(input_path):
                labels[label] = input_path
        # Cover the "no tempN_label files at all, but tempN_input exists" case
        # (older k8temp). Walk tempN_input files we haven't picked up.
        for fname in files:
            if fname.startswith("temp") and fname.endswith("_input") and fname[temp_len:-input_suffix_len].isdigit():
                n = fname[temp_len:-input_suffix_len]
                fallback_label = f"temp{n}"
                if fallback_label not in labels and not any(p.endswith(f"/temp{n}_input") for p in labels.values()):
                    labels[fallback_label] = os.path.join(entry.path, fname)
        if not labels:
            continue
        candidates.append((entry.path, name, labels))

    # Group candidates by chip name to compute alphabetical fallback indexes
    # per type (so two k10temp chips get fallbacks 0 and 1, and the same for
    # two coretemp chips).
    type_indexes: dict[str, int] = collections.defaultdict(int)
    chips: list[_Chip] = []
    for hwmon_path, name, labels in candidates:
        fallback_index = type_indexes[name]
        type_indexes[name] += 1
        package_id = _resolve_chip_package(hwmon_path, name, labels, fallback_index)
        chips.append(
            _Chip(
                hwmon_path=hwmon_path,
                name=name,
                package_id=package_id,
                label_to_input=tuple(sorted(labels.items())),
            )
        )

    return tuple(chips)


def _read_chip_temps(chip: _Chip) -> dict[str, float]:
    """Read live temperatures for one chip. Called every tick; not cached.

    Each ``tempN_input`` file holds an integer in **millidegrees Celsius**
    (kernel-wide hwmon convention -- avoids float math in the kernel).
    We divide by ``MILLIDEG`` (1000) to surface a plain Celsius float
    to consumers, matching the shape they're used to.

    The label/path pairs were resolved once at discovery time and live
    on ``chip.label_to_input``, so this function does no string parsing
    or path walking -- just N file reads and N divisions.

    Tolerant to disappearing sensors
    --------------------------------
    If a thermal driver gets unloaded mid-process (rare on TrueNAS but
    possible) the cached ``tempN_input`` paths go stale. We swallow
    ``FileNotFoundError`` / ``OSError`` per-label inside
    :func:`_helpers._read_int` and simply skip the missing ones; the
    aggregate path then falls through to the all-zero default if every
    chip went away.
    """
    out: dict[str, float] = {}
    for label, input_path in chip.label_to_input:
        v = _read_int(input_path)
        if v is not None:
            out[label] = v / MILLIDEG
    return out
