from middlewared.service_exception import CallError


class ServiceChangeMixin:
    async def _service_change(self, service, verb):

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
            started = await self.middleware.call(f'service.{verb}', service)

            if not started:
                raise CallError(
                    f'The {service} service failed to start',
                    CallError.ESERVICESTARTFAILURE,
                    [service],
                )
