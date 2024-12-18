import os

from middlewared.service import Service
from middlewared.service_exception import ValidationError
from middlewared.utils.functools_ import cache


class SysfsCpuObj:
    BASE = "/sys/devices/system/cpu/"
    GOVERNOR_BASE = os.path.join(BASE, "cpu0/cpufreq")
    CURRENT_GOVERNOR = os.path.join(GOVERNOR_BASE, "scaling_governor")
    GOVERNORS_AVAIL = os.path.join(GOVERNOR_BASE, "scaling_available_governors")


class HardwareCpuService(Service):
    class Config:
        private = True
        namespace = "hardware.cpu"
        cli_namespace = "system.hardware.cpu"

    @cache
    def available_governors(self) -> dict[str, str] | dict:
        """Return available cpu governors"""
        try:
            with open(SysfsCpuObj.GOVERNORS_AVAIL) as f:
                return {i: i for i in f.read().split()}
        except FileNotFoundError:
            # doesn't support changing governor
            return dict()

    def current_governor(self) -> str | None:
        """Returns currently set cpu governor"""
        try:
            with open(SysfsCpuObj.CURRENT_GOVERNOR) as f:
                return f.read().strip()
        except FileNotFoundError:
            # doesn't support changing governor
            return

    def set_governor(self, governor: str) -> None:
        """Set the cpu governor to `governor` on all cpus.
        Available governors may be determined by calling hardware.cpu.available_governors.
        """
        curr_gov = self.current_governor()
        if curr_gov is None:
            raise ValidationError(
                "hardware.cpu.governor", "Changing cpu governor is not supported"
            )
        elif curr_gov == governor:
            # current governor is already set to what is being requested
            return
        elif governor not in self.available_governors():
            raise ValidationError(
                "hardware.cpu.governor", f"{governor} is not available"
            )

        try:
            with os.scandir(SysfsCpuObj.BASE) as sdir:
                for i in filter(
                    lambda x: x.is_dir() and x.name.startswith("cpu"), sdir
                ):
                    with open(
                        os.path.join(i.path, "cpufreq/scaling_governonr"), "w"
                    ) as f:
                        f.write(governor)
        except FileNotFoundError:
            pass
