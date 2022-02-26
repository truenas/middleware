import subprocess

from middlewared.schema import accepts, Dict, returns
from middlewared.service import private, Service
from middlewared.utils import Popen


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
        pipe = await Popen(
            'find /usr/share/zoneinfo/ -type f -not -name zone.tab -not -regex \'.*/Etc/GMT.*\'',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        choices = (await pipe.communicate())[0].decode().strip().split('\n')
        return {
            x[20:]: x[20:] for x in choices if (
                not x[20:].startswith(('right/', 'posix/')) and '.' not in x[20:]
            )
        }
