# -*- coding=utf-8 -*-
import glob
import logging
import re
import subprocess

from middlewared.service import CallError, private, Service

logger = logging.getLogger(__name__)


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
                    size = 32
                elif "vendor: 2c80 device: 4e36" in ixnvdimm:
                    size = 16
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
                    "firmware_version": version,
                })

            self.DATA = result
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
