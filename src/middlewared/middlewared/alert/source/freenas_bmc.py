import re
import subprocess

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource

URL = "https://www.truenas.com/docs/hardware/legacyhardware/miniseries/freenas-minis-2nd-gen/freenasminibmcwatchdog/"


class TrueNASMiniBMCAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Critical IPMI Firmware Update Available"
    text = (
        "A critical IPMI firmware update is available for this system. Please see "
        f"<a href=\"{URL}\" target=\"_blank\">"
        "ASRock Rack C2750D4I BMC Watchdog Issue</a> for details."
    )
    products = ("SCALE",)


class TrueNASMiniBMCAlertSource(ThreadedAlertSource):
    products = ("SCALE",)

    def check_sync(self):
        data = self.middleware.call_sync('system.dmidecode_info')
        systemname = data['system-product-name']
        boardname = data['baseboard-product-name']

        if "freenas" in systemname.lower() and boardname == "C2750D4I":
            mcinfo = subprocess.run(
                ["ipmitool", "mc", "info"],
                capture_output=True, text=True,
            ).stdout
            reg = re.search(r"Firmware Revision.*: (\S+)", mcinfo, flags=re.M)
            if not reg:
                return
            fwver = reg.group(1)
            try:
                fwver = [int(i) for i in fwver.split(".")]
            except ValueError:
                return

            if len(fwver) < 2 or not (fwver[0] == 0 and fwver[1] < 30):
                return

            return Alert(TrueNASMiniBMCAlertClass)
