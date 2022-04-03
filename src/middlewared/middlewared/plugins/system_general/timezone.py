import os

from middlewared.schema import accepts, Dict, returns
from middlewared.service import private, Service


class SystemGeneralService(Service):

    TIMEZONE_CHOICES = None

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('system_timezone_choices', additional_attrs=True, title='System Timezone Choices'))
    async def timezone_choices(self):
        """
        Returns time zone choices.
        """
        if not self.TIMEZONE_CHOICES:
            self.TIMEZONE_CHOICES = await self.get_timezone_choices()

        return self.TIMEZONE_CHOICES

    @private
    async def get_timezone_choices(self):
        timezones = {}
        basepath = '/usr/share/zoneinfo/'
        for root, dirs, files in os.walk(basepath):
            relpath = os.path.normpath(os.path.relpath(root, basepath))
            for timezone in (files if 'right' not in relpath and 'posix' not in relpath else []):
                if relpath != '.':
                    zone_name = f'{relpath}/{timezone}'
                else:
                    zone_name = timezone
                if 'Etc/GMT' not in zone_name:
                    timezones[zone_name] = zone_name
        return timezones
