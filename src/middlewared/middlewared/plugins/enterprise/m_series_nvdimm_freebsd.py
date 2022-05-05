from datetime import datetime
import glob
import re
import subprocess

from middlewared.service import CallError, private, Service


class EnterpriseService(Service):

    DATA = None
    IS_OLD_BIOS_VERSION = False
    ERROR = "Data not retrieved yet"

    @private
    def setup_m_series_nvdimm(self):
        try:
            result = []

            for nvdimm in glob.glob("/dev/nvdimm*"):
                ixnvdimm = subprocess.run(["ixnvdimm", nvdimm], encoding="utf-8", errors="ignore",
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT).stdout
                if "vendor: 2c80 device: 4e32" in ixnvdimm:
                    size = 16
                    clock_speed = 2666
                elif "vendor: 2c80 device: 4e36" in ixnvdimm:
                    size = 16
                    clock_speed = 2933
                elif "vendor: 2c80 device: 4e33" in ixnvdimm:
                    size = 32
                    clock_speed = 2933
                else:
                    continue

                if m := re.search(r"selected: [0-9]+ running: ([0-9]+)", ixnvdimm):
                    running_slot = int(m.group(1))
                else:
                    self.IS_OLD_BIOS_VERSION = True
                    self.DATA = []
                    return

                if m := re.search(rf"slot{running_slot}: ([0-9])([0-9])", ixnvdimm):
                    version = f"{m.group(1)}.{m.group(2)}"
                else:
                    raise CallError(f"Invalid ixnvdimm output for {nvdimm}")

                result.append({
                    "index": int(nvdimm[len("/dev/nvdimm"):]),
                    "size": size,
                    "clock_speed": clock_speed,
                    "firmware_version": version,
                })

            self.DATA = result

            bios_dates = {
                "TRUENAS-M40": datetime(2020, 2, 20),
                "TRUENAS-M50": datetime(2020, 12, 3),
                "TRUENAS-M60": datetime(2020, 12, 3),
            }
            hardware = self.middleware.call_sync("truenas.get_chassis_hardware")
            if min_bios_date := bios_dates.get(hardware):
                dmidecode = self.middleware.call_sync('system.dmidecode_info')['release-date']
                m = re.search(r"Release Date: (?P<m>[0-9]{2})/(?P<d>[0-9]{2})/(?P<y>[0-9]{4})", dmidecode)
                bios_date = datetime(int(m.group("y")), int(m.group("m")), int(m.group("d")))
                self.IS_OLD_BIOS_VERSION = bios_date < min_bios_date
        except Exception as e:
            self.middleware.logger.error("Unhandled exception in enterprise.setup_m_series_nvdimm", exc_info=True)
            self.ERROR = str(e)

    @private
    async def m_series_is_old_bios_version(self):
        return self.IS_OLD_BIOS_VERSION

    @private
    async def m_series_nvdimm(self):
        if self.DATA is None:
            raise CallError(self.ERROR)

        return self.DATA


async def setup(middleware):
    if (await middleware.call("truenas.get_chassis_hardware")).startswith("TRUENAS-M"):
        await middleware.call("enterprise.setup_m_series_nvdimm")
