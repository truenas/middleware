"""CPU topology and temperature utilities.

Sub-module layout:
    _helpers      -- low-level sysfs / parsing helpers
    info          -- CPU topology (``/proc/cpuinfo`` + sysfs walk)
    hwmon         -- ``/sys/class/hwmon`` chip discovery + reading
    amd           -- AMD k10temp / k8temp temperature attribution
    intel         -- Intel coretemp temperature attribution
    temperatures  -- public ``get_cpu_temperatures()`` orchestrator
"""

from .info import CpuFlags, CpuInfo, cpu_flags, cpu_info, cpu_info_impl
from .temperatures import get_cpu_temperatures

__all__ = (
    "CpuFlags",
    "CpuInfo",
    "cpu_flags",
    "cpu_info",
    "cpu_info_impl",
    "get_cpu_temperatures",
)
