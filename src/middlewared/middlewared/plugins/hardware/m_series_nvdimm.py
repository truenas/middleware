import glob
import re
import subprocess

from middlewared.service import Service


class MseriesNvdimmService(Service):

    class Config:
        private = True
        namespace = 'mseries.nvdimm'

    def run_ixnvdimm(self, nvmem_dev):
        return subprocess.run(
            ["ixnvdimm", nvmem_dev],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="ignore",
        ).stdout

    def get_size_and_clock_speed(self, output):
        size = clock_speed = None
        if "vendor: 2c80 device: 4e32" in output:
            size = 16
            clock_speed = 2666
        elif "vendor: 2c80 device: 4e36" in output:
            size = 16
            clock_speed = 2933
        elif "vendor: 2c80 device: 4e33" in output:
            size = 32
            clock_speed = 2933

        return size, clock_speed

    def get_firmware_version_and_detect_old_bios(self, output):
        fw_vers = None
        old_bios = False
        if m := re.search(r"selected: [0-9]+ running: ([0-9]+)", output):
            running_slot = int(m.group(1))
            if m := re.search(rf"slot{running_slot}: ([0-9])([0-9])", output):
                fw_vers = f"{m.group(1)}.{m.group(2)}"
        else:
            old_bios = True

        return fw_vers, old_bios

    def get_module_health(self, output):
        if (m := re.search(r"Module Health:[^\n]+", output)):
            return m.group().split("Module Health: ")[-1].strip()

    def info(self):
        results = []
        sys = ("TRUENAS-M40", "TRUENAS-M50", "TRUENAS-M60")
        if not self.middleware.call_sync("truenas.get_chassis_hardware").startswith(sys):
            return results

        try:
            for nmem in glob.glob("/dev/nmem*"):
                output = self.run_ixnvdimm(nmem)
                size, clock_speed = self.get_size_and_clock_speed(output)
                if not all((size, clock_speed)):
                    continue

                fw_vers, old_bios = self.get_firmware_version_and_detect_old_bios(output)

                results.append({
                    "index": int(nmem[len("/dev/nmem"):]),
                    "dev": nmem.removeprefix("/dev/"),
                    "size": size,
                    "module_health": self.get_module_health(output),
                    "clock_speed": clock_speed,
                    "firmware_version": fw_vers,
                    "old_bios": old_bios,
                })
        except Exception:
            self.logger.error("Unhandled exception obtaining nvdimm info", exc_info=True)
        else:
            return results
