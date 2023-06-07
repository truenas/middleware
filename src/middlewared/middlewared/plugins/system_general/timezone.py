from subprocess import run

from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service
from middlewared.utils.functools import cache


class SystemGeneralService(Service):

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('system_timezone_choices', additional_attrs=True, title='System Timezone Choices'))
    @cache
    def timezone_choices(self):
        """Returns available timezones"""
        choices = dict()
        for i in run(['timedatectl', 'list-timezones'], capture_output=True).stdout.decode().split('\n'):
            if (choice := i.strip()):
                choices[choice] = choice
        return choices
