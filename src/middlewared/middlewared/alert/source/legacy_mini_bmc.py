from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert
from middlewared.plugins.system.product import ProductType

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
    products = (ProductType.SCALE,)


class TrueNASMiniBMCAlertSource(AlertSource):
    products = (ProductType.SCALE,)

    async def check(self):
        dmi = await self.middleware.call("system.dmidecode_info")
        if "freenas" in dmi["system-product-name"].lower() and dmi["baseboard-product-name"] == "C2750D4I":
            if (fwver := (await self.middleware.call("ipmi.mc.info")).get("firmware_revision", None)):
                try:
                    fwver = [int(i) for i in fwver.split(".")]
                    if len(fwver) < 2 or not (fwver[0] == 0 and fwver[1] < 30):
                        return
                except ValueError:
                    return

            return Alert(TrueNASMiniBMCAlertClass)
