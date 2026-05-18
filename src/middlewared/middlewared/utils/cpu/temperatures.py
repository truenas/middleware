"""Top-level orchestrator: produce the per-logical-CPU temperature dict.

The pipeline:
  1. ``cpu_info()`` gives us full kernel topology (logical_to_phys,
     phys_to_package, phys_to_die, phys_to_core_id).
  2. ``_phys_indexes()`` derives small lookup tables once per process.
  3. ``_discover_cpu_chips()`` returns the CPU thermal chips on the system,
     each annotated with its resolved ``package_id`` and pre-resolved
     ``tempN_input`` paths.
  4. For each chip we read the live temperatures and dispatch to the
     vendor-specific attribution routine (``amd._amd_assignments``,
     ``intel._intel_assignments``, or the generic single-temp fallback).
     Each routine returns ``dict[phys_idx, float]``.
  5. We project per-physical-core temps onto every online logical CPU
     using ``logical_to_phys`` -- no mirror loop, no SMT-arity assumptions.
  6. Aggregate ``'cpu'`` is the mean of physical-core temps (so asymmetric
     SMT doesn't bias the average toward HT-paired cores).
"""

import collections
from dataclasses import dataclass
import functools

from ._helpers import _numeric
from .amd import AMD_PREFIXES, _amd_assignments
from .hwmon import _discover_cpu_chips, _read_chip_temps
from .info import cpu_info
from .intel import _intel_assignments


@dataclass(frozen=True)
class _PhysIndexes:
    pkg_to_phys: dict[int, list[int]]
    """package_id -> list of physical-core ordinals in that package."""
    pkg_die_to_phys: dict[tuple[int, int], list[int]]
    """(package_id, die_id) -> list of physical-core ordinals."""
    pkg_core_to_phys: dict[int, dict[int, int]]
    """package_id -> {core_id: phys_idx} for matching coretemp 'Core N'."""


@functools.cache
def _phys_indexes() -> _PhysIndexes:
    cinfo = cpu_info()
    pkg_to_phys: dict[int, list[int]] = collections.defaultdict(list)
    pkg_die_to_phys: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    pkg_core_to_phys: dict[int, dict[int, int]] = collections.defaultdict(dict)
    for phys, pkg in cinfo["phys_to_package"].items():
        pkg_to_phys[pkg].append(phys)
        pkg_die_to_phys[(pkg, cinfo["phys_to_die"][phys])].append(phys)
        pkg_core_to_phys[pkg][cinfo["phys_to_core_id"][phys]] = phys
    return _PhysIndexes(
        pkg_to_phys=dict(pkg_to_phys),
        pkg_die_to_phys=dict(pkg_die_to_phys),
        pkg_core_to_phys={k: dict(v) for k, v in pkg_core_to_phys.items()},
    )


def _generic_single_temp_assignments(
    chip_data: dict[str, float],
    chip_pkg: int,
    pkg_to_phys: dict[int, list[int]],
) -> dict[int, float]:
    """via_cputemp / cpu_thermal: a single-temp chip; broadcast temp1 across
    every physical core in the chip's package."""
    out: dict[int, float] = {}
    t = _numeric(chip_data, "temp1")
    if t is None:
        return out
    for phys in pkg_to_phys.get(chip_pkg, ()):
        out.setdefault(phys, t)
    return out


def get_cpu_temperatures() -> dict[str, float]:
    """Produce the per-logical-CPU temperature snapshot for the dashboard.

    Return shape (held stable for backwards compatibility -- netdata's
    ``cputemp.temperatures`` chart registers one dimension per key on
    its first call)::

        {
          'cpu0': float,                 # one entry per online logical CPU
          'cpu1': float,
          ...
          'cpu<core_count-1>': float,
          'cpu':  float,                 # aggregate across physical cores
        }

    On hardware with no readable thermal sensors, returns the same
    shape with every value set to ``0.0`` so consumers don't lose
    chart dimensions.

    The complete chain
    ------------------
    Step 1 -- topology (kernel truth, cached once)
        :func:`info.cpu_info` walks ``/sys/devices/system/cpu/cpuN/topology/``
        and ``/proc/cpuinfo`` once per process to build:

        - ``logical_to_phys``    -- ``cpuN -> physical-core ordinal``
        - ``phys_to_package``    -- physical core -> socket
        - ``phys_to_die``        -- physical core -> die_id (CCD on AMD Zen)
        - ``phys_to_core_id``    -- physical core -> package-relative core_id

        These four maps are everything the rest of the chain needs to
        decide where each thermal reading belongs.

    Step 2 -- index pre-build (cached once)
        :func:`_phys_indexes` flips those maps into the lookups the
        attribution routines actually want:

        - ``pkg_to_phys``        -- "cores in this package"
        - ``pkg_die_to_phys``    -- "cores on this die in this package" (AMD)
        - ``pkg_core_to_phys``   -- "core_id N within this package" (Intel)

    Step 3 -- chip discovery (cached once)
        :func:`hwmon._discover_cpu_chips` enumerates
        ``/sys/class/hwmon/`` and produces a tuple of :class:`_Chip`
        records, each carrying its resolved ``package_id`` and
        pre-bound ``(label, tempN_input path)`` pairs.

    Step 4 -- read live temperatures
        For each chip, :func:`hwmon._read_chip_temps` opens its
        ``tempN_input`` files and returns a fresh
        ``{label: celsius}`` dict.

    Step 5 -- vendor-specific attribution
        Per-chip dispatch into the routine that understands its
        labelling convention:

        - ``k10temp`` / ``k8temp`` -> :func:`amd._amd_assignments`
          (Tctl / Tdie / Tccd<N> / temp1 cascade with per-CCD
          attribution by ``die_id`` and a package-wide fallback).
        - ``coretemp`` -> :func:`intel._intel_assignments` (per-core
          DTS readings matched by ``core_id`` within the chip's
          package).
        - everything else (``via_cputemp``, ``cpu_thermal``) ->
          :func:`_generic_single_temp_assignments` (broadcast
          ``temp1`` across the package).

        Every routine returns ``dict[phys_idx, float]``: per-physical-
        core temperatures, with no logical-CPU knowledge whatsoever.

    Step 6 -- project to logical CPUs
        Iterate ``logical_to_phys`` and assign each online logical CPU
        the temperature of its physical core. This single loop replaces
        the old "primary-write + ``ht_map`` mirror" pattern entirely,
        which means SMT arity is no longer a special case: 1-way
        (SMT off), 2-way (typical x86), 4-way (POWER), and partial
        SMT all just work.

    Step 7 -- aggregate
        ``data['cpu']`` is the mean of physical-core temperatures, not
        the mean of logical-CPU temperatures. This avoids the bias an
        asymmetric SMT layout (some cores 2-way, some 1-way) would
        otherwise introduce, and is mathematically immune to
        upstream bugs that produce overlapping per-logical-CPU keys
        (the original 1.5xTctl bug class).

    Why this works for every supported CPU
    --------------------------------------
    The pipeline never assumes a sibling-mirror, an even CCD split,
    or a chip-to-package alphabetical order. Every attribution
    decision is made from kernel-published topology fields plus the
    chip's own labels:

    - **AMD APU with only Tctl** -- step 5 broadcasts Tctl across
      every physical core in the package via the package fallback;
      step 6 mirrors to all logical CPUs in each core.
    - **AMD multi-CCD** -- per-die attribution by ``die_id``;
      asymmetric or partially-fused CCDs handled by construction.
    - **AMD multi-socket EPYC** -- ``hwmon._resolve_chip_package``
      assigns each ``k10temp-pci-*`` chip its own ``physical_package_id``
      via the PCI device's ``numa_node``, so socket-0 readings can't
      overwrite socket-1 readings.
    - **Intel single or multi-socket** -- ``"Package id N"`` labels
      drive package resolution; ``"Core N"`` labels drive per-core
      attribution within the package via ``core_id``.
    - **4-way SMT (POWER)** -- ``logical_to_phys`` carries every
      online sibling, no mirror loop to break.
    - **Partial SMT (some siblings offline)** -- same; only online
      logical CPUs appear in ``logical_to_phys``.
    - **No CPU thermal driver loaded** -- ``_discover_cpu_chips``
      returns ``()``; we emit the all-zero fallback so the
      dashboard's chart shape stays stable.
    """
    cinfo = cpu_info()
    chips = _discover_cpu_chips()
    indexes = _phys_indexes()

    # 1. Per-physical-core temperatures from every chip.
    phys_temps: dict[int, float] = {}
    for chip in chips:
        chip_data = _read_chip_temps(chip)
        if not chip_data:
            continue
        if chip.name in AMD_PREFIXES:
            phys_temps.update(
                _amd_assignments(
                    chip_data,
                    chip.package_id,
                    cinfo["cpu_model"],
                    indexes.pkg_to_phys,
                    indexes.pkg_die_to_phys,
                )
            )
        elif chip.name == "coretemp":
            phys_temps.update(
                _intel_assignments(
                    chip_data,
                    indexes.pkg_core_to_phys.get(chip.package_id, {}),
                )
            )
        else:
            phys_temps.update(
                _generic_single_temp_assignments(
                    chip_data,
                    chip.package_id,
                    indexes.pkg_to_phys,
                )
            )

    # 2. Project onto every online logical CPU.
    data: dict[str, float] = {}
    for logical_id, phys in cinfo["logical_to_phys"].items():
        t = phys_temps.get(phys)
        if t is not None:
            data[f"cpu{logical_id}"] = t

    # 3. Aggregate across physical cores (so asymmetric SMT doesn't bias
    #    the mean toward HT-paired cores).
    if data and phys_temps:
        data["cpu"] = sum(phys_temps.values()) / len(phys_temps)
        return data

    return {f"cpu{i}": 0.0 for i in range(cinfo["core_count"] or 0)} | {"cpu": 0.0}
