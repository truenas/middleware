from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.service.services.base import SimpleService
from middlewared.service_exception import CallError


class TruesearchService(SimpleService):
    name = "truesearch"

    etc = ["truesearch"]
    reloadable = True
    may_run_on_standby = False

    systemd_unit = "truesearch"

    async def before_start(self) -> None:
        if not await self.call2(self.s.truenas.entitlements.serving, LicenseFeature.TRUESEARCH):
            raise CallError('System is not licensed to use TrueSearch')
