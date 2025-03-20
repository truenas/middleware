from middlewared.api import api_method
from middlewared.api.current import (
    SystemGeneralTimezoneChoicesArgs,
    SystemGeneralTimezoneChoicesResult,
)
from middlewared.service import Service
from middlewared.utils.timezone_choices import tz_choices


class SystemGeneralService(Service):

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @api_method(
        SystemGeneralTimezoneChoicesArgs,
        SystemGeneralTimezoneChoicesResult
    )
    def timezone_choices(self):
        """Returns available timezones"""
        return dict(tz_choices())
