import json
import subprocess
import threading
import time

from middlewared.service import private, Service


class ReportingService(Service):
    CACHE = None
    CACHE_LOCK = threading.Lock()
    CACHE_TIME = None
    LOGGED_ERROR = False

    @private
    def cpu_temperatures(self):
        with self.CACHE_LOCK:
            if self.CACHE_TIME is None or time.monotonic() - self.CACHE_TIME >= 60:
                try:
                    self.CACHE = self.cpu_temperatures_internal()
                except Exception:
                    self.CACHE = {}
                    if not self.LOGGED_ERROR:
                        self.middleware.logger.error("Error gathering CPU temperatures", exc_info=True)
                        self.LOGGED_ERROR = True

                self.CACHE_TIME = time.monotonic()

            return self.CACHE

    @private
    def cpu_temperatures_internal(self):
        temperature = {}
        cp = subprocess.run(["sensors", "-j"], capture_output=True, text=True)
        sensors = json.loads(cp.stdout)
        amd_sensor = sensors.get("k10temp-pci-00c3")
        if amd_sensor:
            temperature = self._amd_cpu_temperature(amd_sensor)
        else:
            core = 0
            for chip, value in sensors.items():
                for name, temps in value.items():
                    if not name.startswith("Core "):
                        continue
                    for temp, value in temps.items():
                        if "input" in temp:
                            temperature[core] = value
                            core += 1
                            break

        return temperature

    AMD_PREFER_TDIE = (
        # https://github.com/torvalds/linux/blob/master/drivers/hwmon/k10temp.c#L121
        # static const struct tctl_offset tctl_offset_table[] = {
        "AMD Ryzen 5 1600X",
        "AMD Ryzen 7 1700X",
        "AMD Ryzen 7 1800X",
        "AMD Ryzen 7 2700X",
        "AMD Ryzen Threadripper 19",
        "AMD Ryzen Threadripper 29",
    )
    AMD_SYSTEM_INFO = None

    def _amd_cpu_temperature(self, amd_sensor):
        if self.AMD_SYSTEM_INFO is None:
            self.AMD_SYSTEM_INFO = self.middleware.call_sync("system.cpu_info")

        cpu_model = self.AMD_SYSTEM_INFO["cpu_model"]
        core_count = self.AMD_SYSTEM_INFO["physical_core_count"]

        ccds = []
        for k, v in amd_sensor.items():
            if k.startswith("Tccd") and v:
                t = list(v.values())[0]
                if isinstance(t, (int, float)):
                    ccds.append(t)
        has_tdie = (
            "Tdie" in amd_sensor and
            amd_sensor["Tdie"] and
            isinstance(list(amd_sensor["Tdie"].values())[0], (int, float))
        )
        if cpu_model.startswith(self.AMD_PREFER_TDIE) and has_tdie:
            return self._amd_cpu_tdie_temperature(amd_sensor, core_count)
        elif ccds and core_count % len(ccds) == 0:
            return dict(enumerate(sum([[t] * (core_count // len(ccds)) for t in ccds], [])))
        elif has_tdie:
            return self._amd_cpu_tdie_temperature(amd_sensor, core_count)
        elif (
            "Tctl" in amd_sensor and
            amd_sensor["Tctl"] and
            isinstance(list(amd_sensor["Tctl"].values())[0], (int, float))
        ):
            return dict(enumerate([list(amd_sensor["Tctl"].values())[0]] * core_count))
        elif "temp1" in amd_sensor and "temp1_input" in amd_sensor["temp1"]:
            return dict(enumerate([amd_sensor["temp1"]["temp1_input"]] * core_count))

    def _amd_cpu_tdie_temperature(self, amd_sensor, core_count):
        return dict(enumerate([list(amd_sensor["Tdie"].values())[0]] * core_count))
