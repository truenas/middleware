from typing import Literal

from middlewared.service_exception import CallError
from middlewared.utils.service.call_mixin import CallMixin


class ServiceChangeMixin(CallMixin):
    async def _service_change(
        self,
        service: str,
        verb: Literal['restart', 'reload'],
        options: dict | None = None,
    ) -> None:

        svc_state = (await self.middleware.call(
            'service.query',
            [('service', '=', service)],
            {'get': True}
        ))['state'].lower()

        # For now its hard to keep track of which services change rc.conf.
        # To be safe run this every time any service is updated.
        # This adds up ~180ms so its seems a reasonable workaround for the time being.
        await self.middleware.call('etc.generate', 'rc')

        if svc_state == 'running':
            started = await (
                await self.middleware.call('service.control', verb.upper(), service, options or {})
            ).wait(raise_error=True)

            if not started:
                raise CallError(
                    f'The {service} service failed to start',
                    CallError.ESERVICESTARTFAILURE,
                    [service],
                )
