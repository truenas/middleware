"""AMD k10temp / k8temp temperature attribution.

``AMD_PREFER_TDIE`` mirrors the kernel's ``tctl_offset_table`` in
``drivers/hwmon/k10temp.c``. For chips in this list, ``Tdie`` is the
offset-corrected die temperature and is preferred over ``Tctl`` (which
carries a fan-control offset, e.g. +27 deg on Zen1 Threadrippers — see
NAS-110515).

Per-CCD attribution uses the kernel's ``die_id``: ``Tccd<N>`` is mapped
to the physical cores whose ``die_id == N - 1`` within the matching
package. This is a high-confidence hypothesis (the k10temp driver
registers Tccd labels in hardware-slot order, and ``die_id`` derives
from the same firmware enumeration on every Zen system observed in the
wild) but it is not a kernel contract.
"""

import re

from ._helpers import _numeric

AMD_PREFER_TDIE = (
    # https://github.com/torvalds/linux/blob/master/drivers/hwmon/k10temp.c
    # static const struct tctl_offset tctl_offset_table[] = {
    "AMD Ryzen 5 1600X",
    "AMD Ryzen 7 1700X",
    "AMD Ryzen 7 1800X",
    "AMD Ryzen 7 2700X",
    "AMD Ryzen Threadripper 19",
    "AMD Ryzen Threadripper 29",
)
AMD_PREFIXES = ("k8temp", "k10temp")

RE_TCCD = re.compile(r"Tccd(\d+)")


def _amd_assignments(
    chip_data: dict[str, float],
    chip_pkg: int,
    cpu_model: str | None,
    pkg_to_phys: dict[int, list[int]],
    pkg_die_to_phys: dict[tuple[int, int], list[int]],
) -> dict[int, float]:
    """Map a k10temp/k8temp chip's labels onto physical-core ordinals.

    What the labels actually mean
    -----------------------------
    AMD's k10temp driver can expose up to four kinds of temperature on
    a given package; which ones are present depends on the silicon and
    the kernel:

    - **Tctl ("Control Temperature")** -- the value the SoC uses for
      fan curves. On most Zen2+ chips it's the same as Tdie. On
      certain Zen1 / Zen+ chips (the ``AMD_PREFER_TDIE`` list, which
      mirrors the kernel's ``tctl_offset_table``) Tctl is offset from
      reality by +10..+27 deg C so fans ramp earlier; on those parts
      Tctl is *not* a meaningful "CPU temperature" reading.
    - **Tdie ("Die Temperature")** -- the actual silicon temperature
      after the fan-control offset has been removed. The kernel only
      exposes Tdie when an offset entry exists for the model, so the
      presence of Tdie is the signal that "Tctl is offset, prefer me".
    - **Tccd<N> ("CCD Temperature")** -- on Zen2+ chiplet CPUs each
      Core Complex Die has its own thermal sensor. Tccd1 is the first
      CCD, Tccd2 the second, and so on. Boxes without chiplets (APUs,
      monolithic dies) don't expose any Tccd labels.
    - **temp1** -- the legacy k8temp / generic fallback label for
      pre-Zen AMD parts that only have one thermal sensor on the
      whole package.

    Selection logic (preserves NAS-110515 behavior)
    -----------------------------------------------
    1. **AMD_PREFER_TDIE + Tdie present** -- Tdie wins for every
       physical core in the package. Tccd readings are skipped even
       when present, because on those Zen1 SKUs Tccd is rare/unused
       and Tdie is the canonical accurate value.
    2. **Per-CCD attribution** -- otherwise, for each ``Tccd<N>`` we
       assign that reading to every physical core whose ``die_id ==
       N - 1`` within the chip's package. This is *the* hypothesis
       this code rests on: the kernel's k10temp driver registers Tccd
       channels in CCD hardware-slot order, and the same firmware
       enumeration drives ``die_id`` from sysfs, so on every Zen
       system observed in the wild they match.
    3. **Package-wide fallback** -- any physical core in the package
       that didn't get a Tccd reading falls back to the first
       available of Tdie / Tctl / temp1. This handles non-chiplet
       parts (APUs reporting only Tctl), partial-CCD coverage (e.g.
       Tccd1 reported but Tccd2 missing), and k8temp-era chips
       (temp1 only).

    Why this is robust across the AMD lineup
    ----------------------------------------
    - **5825U-class APU** (Tctl only) -> step 3 broadcasts Tctl to
      every core in the package.
    - **Ryzen 9 multi-CCD** (Tccd1 + Tccd2) -> step 2 splits cores
      across CCDs by ``die_id``; no even-split assumption.
    - **Asymmetric / partially-fused CCD** -> step 2 only fills the
      cores that actually exist in each die; step 3 covers any
      uncovered cores.
    - **Threadripper 1950X** (in ``AMD_PREFER_TDIE``) -> step 1
      sidesteps Tctl's +27 deg offset and uses Tdie everywhere.
    - **Dual-socket EPYC** -> ``chip_pkg`` is resolved per chip in
      ``hwmon._resolve_chip_package``, so each chip's labels only
      reach the cores in its own package.
    """
    out: dict[int, float] = {}

    tdie = _numeric(chip_data, "Tdie")
    tctl = _numeric(chip_data, "Tctl")
    temp1 = _numeric(chip_data, "temp1")
    prefer_tdie = cpu_model is not None and cpu_model.startswith(AMD_PREFER_TDIE) and tdie is not None

    # Step 1: per-CCD assignments (skipped on AMD_PREFER_TDIE + Tdie).
    # HYPOTHESIS: k10temp's Tccd<N> corresponds to kernel die_id == N - 1.
    # k10temp_get_ccd_support() iterates i=0..limit and sets BIT(TCCD_BIT(i))
    # in hardware-slot order; die_id is derived from the same firmware
    # enumeration on every Zen system observed in the wild.
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
        package_temp = next(
            (t for t in (tdie, tctl, temp1) if t is not None),
            None,
        )
    if package_temp is not None:
        for phys in pkg_to_phys.get(chip_pkg, ()):
            out.setdefault(phys, package_temp)

    return out
