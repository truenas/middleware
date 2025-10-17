import contextlib

from .constants import NVMET_SERVICE_NAME


class NVMetStandbyMixin:

    @contextlib.asynccontextmanager
    async def _handle_standby_service_state(self, check=False):
        if check:
            old_state = await self.middleware.call('nvmet.global.ana_active')
        yield
        # If no exception was thrown, then do the post check if requested
        if check:
            new_state = await self.middleware.call('nvmet.global.ana_active')
            if old_state != new_state:
                if new_state:
                    # Start on STANDBY node
                    await self.middleware.call(
                        'failover.call_remote',
                        'service.control',
                        ['START', NVMET_SERVICE_NAME, {'ha_propagate': False}],
                        {'job': True}
                    )
                else:
                    # Stop on STANDBY node
                    await self.middleware.call(
                        'failover.call_remote',
                        'service.control',
                        ['STOP', NVMET_SERVICE_NAME, {'ha_propagate': False}],
                        {'job': True}
                    )
