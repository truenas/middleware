from middlewared.api import api_method
from middlewared.api.current import (
    SystemGeneralKbdMapChoicesArgs,
    SystemGeneralKbdMapChoicesResult,
)
from middlewared.service import Service
from middlewared.utils.kbdmap_choices import kbdmap_choices


class SystemGeneralService(Service):
    class Config:
        namespace = "system.general"
        cli_namespace = "system.general"

    @api_method(
        SystemGeneralKbdMapChoicesArgs,
        SystemGeneralKbdMapChoicesResult,
    )
    async def kbdmap_choices(self):
        """Returns keyboard map choices."""
        return dict(sorted(kbdmap_choices(), key=lambda x: x[1]))
