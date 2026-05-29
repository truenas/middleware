"""CPU topology and metadata.

``cpu_info()`` walks ``/sys/devices/system/cpu/cpuN/topology/`` and
``/proc/cpuinfo`` once per process to build a ``CpuInfo`` TypedDict that
includes every mapping the temperature pipeline needs:

  - ``logical_to_phys``   -- every online logical CPU id -> physical-core ordinal
  - ``phys_to_package``   -- physical-core ordinal -> physical_package_id
  - ``phys_to_die``       -- physical-core ordinal -> die_id within its package
                              (on AMD Zen this is the CCD index)
  - ``phys_to_core_id``   -- physical-core ordinal -> core_id within its package
                              (used to match Intel coretemp 'Core N' labels)

``cpu_flags()`` is a separate cached reader of ``/proc/cpuinfo`` for
external consumers that only need the flag list.
"""

import functools
import os
import typing

from ._helpers import _parse_cpulist, _read_int, _read_str


class CpuInfo(typing.TypedDict):
    cpu_model: str | None
    """The CPU model"""
    vendor_id: str | None
    """The CPU vendor id (e.g. 'GenuineIntel', 'AuthenticAMD')"""
    cpu_flags: tuple[str, ...]
    """The CPU feature flags as reported in /proc/cpuinfo"""
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


def _read_proc_cpuinfo() -> tuple[str | None, str | None, tuple[str, ...]]:
    """Extract (model_name, vendor_id, flags) from /proc/cpuinfo."""
    cm: str | None = None
    vid: str | None = None
    cf: tuple[str, ...] = ()
    with open("/proc/cpuinfo", "rb") as f:
        for line in f:
            if cm is None and line.startswith(b"model name"):
                cm = line.split(b":", 1)[-1].strip().decode() or None
            elif vid is None and line.startswith(b"vendor_id"):
                vid = line.split(b":", 1)[-1].strip().decode() or None
            elif not cf and line.startswith(b"flags"):
                cf = tuple(line.split(b":", 1)[-1].strip().decode().split())
            if cm is not None and vid is not None and cf:
                break
    return cm, vid, cf


@functools.cache
def cpu_info() -> CpuInfo:
    """Cached topology snapshot for the current process.

    CPU topology is fixed once Linux finishes bringing up CPUs at boot
    (the kernel does not re-enumerate cores at runtime), so we walk
    sysfs exactly once per middleware process and reuse the result.

    Vocabulary (matters for understanding the rest of this package):

    - **logical CPU** -- what shows up as ``cpu0``, ``cpu1``, ... in
      Linux. Each entry in ``/sys/devices/system/cpu/cpuN/`` is one
      logical CPU. With SMT/HyperThreading enabled, multiple logical
      CPUs share a single piece of silicon ("physical core").
    - **physical core** -- the actual hardware unit. We assign each
      one a stable ordinal (0..N-1) sorted by lowest logical CPU id.
    - **package** -- a socket. Multi-socket boxes have multiple
      packages; everything else has package 0.
    - **die** -- a piece of silicon within a package. On AMD Zen
      "chiplet" CPUs each CCD (Core Complex Die) is its own die with
      its own thermal sensor; on Intel and most ARM, one die per
      package.
    - **core_id** -- the kernel's package-relative core index, used
      by ``coretemp``'s ``"Core N"`` labels to identify which
      physical core a per-core reading belongs to.

    The four mapping fields it produces all key off the physical-core
    ordinal so the temperature pipeline can answer "which package /
    die / core_id is this physical core in?" in O(1).
    """
    return cpu_info_impl()


def cpu_info_impl() -> CpuInfo:
    cc = os.sysconf("SC_NPROCESSORS_ONLN") or None
    cm, vid, cf = _read_proc_cpuinfo()

    # Walk every online cpuN/topology/ once. core_cpus_list is in Linux
    # cpulist format (https://docs.kernel.org/admin-guide/cputopology.html);
    # examples:
    #   "0,8"   - HT pair where the kernel enumerates siblings non-consecutively
    #   "0-1"   - HT pair where the kernel enumerates siblings consecutively
    #   "0"     - SMT disabled (only the primary thread is online)
    #   "0-3"   - 4-way SMT (POWER) or wider
    core_meta: dict[tuple[int, ...], tuple[int, int, int]] = {}
    with os.scandir("/sys/devices/system/cpu/") as sdir:
        for entry in filter(lambda x: x.is_dir() and x.name.startswith("cpu"), sdir):
            try:
                int(entry.name[len("cpu") :])
            except ValueError:
                # Skip non-numeric subdirs (cpufreq, cpuidle, etc.).
                continue
            topo = os.path.join(entry.path, "topology")
            siblings_str = _read_str(os.path.join(topo, "core_cpus_list"))
            if siblings_str is None:
                continue
            try:
                siblings = _parse_cpulist(siblings_str)
            except ValueError:
                continue
            if not siblings:
                continue
            core_key = tuple(siblings)
            if core_key in core_meta:
                continue  # already recorded via another sibling cpuN dir
            pkg = _read_int(os.path.join(topo, "physical_package_id"))
            die = _read_int(os.path.join(topo, "die_id"))
            cid = _read_int(os.path.join(topo, "core_id"))
            core_meta[core_key] = (
                pkg if pkg is not None and pkg >= 0 else 0,
                die if die is not None and die >= 0 else 0,
                cid if cid is not None and cid >= 0 else 0,
            )

    # Sort physical cores by their lowest logical CPU id for stable ordinals
    # (filesystem iteration order is not guaranteed sorted).
    sorted_cores = sorted(core_meta.keys(), key=min)

    logical_to_phys: dict[int, int] = {}
    phys_to_package: dict[int, int] = {}
    phys_to_die: dict[int, int] = {}
    phys_to_core_id: dict[int, int] = {}
    for phys_idx, core_key in enumerate(sorted_cores):
        for cpu_id in sorted(core_key):
            logical_to_phys[cpu_id] = phys_idx
        pkg, die, cid = core_meta[core_key]
        phys_to_package[phys_idx] = pkg
        phys_to_die[phys_idx] = die
        phys_to_core_id[phys_idx] = cid

    return CpuInfo(
        cpu_model=cm,
        vendor_id=vid,
        cpu_flags=cf,
        core_count=cc,
        physical_core_count=len(sorted_cores),
        logical_to_phys=logical_to_phys,
        phys_to_package=phys_to_package,
        phys_to_die=phys_to_die,
        phys_to_core_id=phys_to_core_id,
    )


@functools.cache
def cpu_flags() -> CpuFlags:
    with open("/proc/cpuinfo", "rb") as f:
        for line in filter(lambda x: x.startswith((b"processor", b"flags")), f):
            parts = line.decode("utf-8").split(":", 1)
            title = parts[0].strip()
            if title == "flags":
                return parts[1].strip().split()
    return []
