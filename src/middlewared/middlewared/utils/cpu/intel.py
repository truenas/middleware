"""Intel coretemp temperature attribution.

The kernel coretemp driver labels are:
  - ``Package id N``  -- the package's overall thermal reading
  - ``Core N``        -- per-physical-core reading, where ``N`` is the
                          ``core_id`` within the package (matched via
                          ``CpuInfo['phys_to_core_id']``).

Only ``Core N`` labels are projected onto physical cores here. The
``Package id N`` label is consumed during chip-to-package resolution in
``hwmon._resolve_chip_package``.
"""

import re

RE_CORE = re.compile(r"^Core ([0-9]+)$")


def _intel_assignments(
    chip_data: dict[str, float],
    pkg_core_index: dict[int, int],
) -> dict[int, float]:
    """Map an Intel coretemp chip's per-core labels onto physical-core ordinals.

    How Intel exposes CPU temperatures
    ----------------------------------
    Unlike AMD k10temp, Intel's coretemp driver gives us an honest
    per-physical-core temperature: every core in the package has its
    own DTS (Digital Thermal Sensor) and the kernel surfaces each one
    individually, labelled ``"Core N"`` where ``N`` is the kernel's
    ``core_id`` -- the *package-relative* core index. The driver also
    emits a ``"Package id N"`` label for the package's overall reading;
    that one is consumed earlier in
    :func:`hwmon._resolve_chip_package` to figure out which package
    this chip serves and is ignored here.

    Why we look up by ``core_id`` and not by logical CPU id
    -------------------------------------------------------
    A ``"Core N"`` label is *not* a logical CPU id (``cpuN``). Two
    different physical cores in different packages can both be
    ``Core 0``. ``core_id`` is package-relative, so to identify a
    physical core globally we need (package_id, core_id) -- which is
    exactly what ``pkg_core_index`` is: the slice of
    :class:`_PhysIndexes.pkg_core_to_phys` for this chip's package,
    pre-built once from ``CpuInfo['phys_to_core_id']``. Lookup is
    O(1) per label.

    Why this works across the Intel lineup
    --------------------------------------
    - **Single-package, HT enabled** -- one chip, every ``Core N``
      maps to one physical core; the upstream caller mirrors each
      reading onto every logical CPU sharing that core via
      ``logical_to_phys``.
    - **Single-package, HT disabled** -- same as above; SMT siblings
      simply don't exist in the topology.
    - **Multi-socket Xeon** -- one chip per package
      (``coretemp-isa-0000``, ``coretemp-isa-0001``, ...), each
      resolved to its real ``physical_package_id`` via the chip's
      own ``"Package id N"`` label, so ``Core 0`` on chip 0 and
      ``Core 0`` on chip 1 land on different physical cores.
    - **Cores with broken DTS** -- silently skipped: a missing
      ``Core N`` simply doesn't appear in ``chip_data``, so the
      affected physical core ends up without a reading and the
      logical-CPU projection in :func:`get_cpu_temperatures` omits
      its ``cpuN`` keys.
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
