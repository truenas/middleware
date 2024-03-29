from middlewared.service import private, Service


class FailoverService(Service):

    @private
    async def retrieve_boot_ids(self):
        return {
            await self.middleware.call('failover.node'): await self.middleware.call('system.boot_id'),
            await self.middleware.call('failover.call_remote', 'failover.node'): await self.middleware.call(
                'failover.call_remote', 'system.boot_id',
            ),
        }
