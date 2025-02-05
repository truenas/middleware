from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service
from middlewared.utils.timezone_choices import tz_choices


class SystemGeneralService(Service):

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('system_timezone_choices', additional_attrs=True, title='System Timezone Choices'))
    def timezone_choices(self):
        """Returns available timezones"""
        return dict(tz_choices())
