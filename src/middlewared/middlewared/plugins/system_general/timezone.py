from functools import cache

from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service


@cache
def tz_choices() -> tuple[tuple[str, str]]:
    # Logic deduced from what timedatectl list-timezones does
    tz = list()
    with open('/usr/share/zoneinfo/tzdata.zi') as f:
        for line in filter(lambda x: x[0] in ('Z', 'L'), f):
            index = 1 if line[0] == 'Z' else 2
            tz_choice = line.split()[index].strip()
            tz.append((tz_choice, tz_choice))
    return tuple(tz)


class SystemGeneralService(Service):

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('system_timezone_choices', additional_attrs=True, title='System Timezone Choices'))
    def timezone_choices(self):
        """Returns available timezones"""
        return dict(tz_choices())
