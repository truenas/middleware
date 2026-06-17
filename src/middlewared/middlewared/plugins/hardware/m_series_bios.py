from __future__ import annotations

import datetime
import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.main import Middleware


@functools.cache
def is_old_version(middleware: Middleware) -> bool:
    chassis = middleware.call_sync("truenas.get_chassis_hardware")
    bios_dates = {
        "TRUENAS-M40": datetime.date(2020, 2, 20),
        "TRUENAS-M50": datetime.date(2020, 12, 3),
        "TRUENAS-M60": datetime.date(2020, 12, 3),
    }
    min_bios_date = next((v for k, v in bios_dates.items() if chassis.startswith(k)), None)
    if min_bios_date and (bios := middleware.call_sync("system.dmidecode_info")["bios-release-date"]):
        return bool(bios < min_bios_date)

    return False
