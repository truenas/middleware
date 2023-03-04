import datetime

from middlewared.service import Service
from middlewared.utils.functools import cache


class MseriesBiosService(Service):

    class Config:
        private = True
        namespace = 'mseries.bios'

    @cache
    def is_old_version(self):
        chassis = self.middleware.call_sync("truenas.get_chassis_hardware")
        if not chassis.startswith(("M40", "M50", "M60")):
            return

        bios_dates = {
            "TRUENAS-M40": datetime.date(2020, 2, 20),
            "TRUENAS-M50": datetime.date(2020, 12, 3),
            "TRUENAS-M60": datetime.date(2020, 12, 3),
        }
        min_bios_date = next((v for k, v in bios_dates.items() if k.startswith(chassis)), None)
        if min_bios_date and (bios := self.middleware.call_sync("system.dmidecode_info")["bios-release-date"]):
            return bios < min_bios_date
