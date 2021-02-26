from middlewared.service import Service


class UsageService(Service):

    FAILED_RETRIES = 3

    class Config:
        private = True

    async def firstboot(self):
        hash = await self.middleware.call('usage.retrieve_system_hash')
        version = (await self.middleware.call('usage.gather_system_version', {}))['version']
        retries = self.FAILED_RETRIES

        while retries:
            try:
                await self.middleware.call('usage.submit_stats', {
                    'platform': 'TrueNAS-SCALE',
                    'system_hash': hash,
                    'firstboot': [{
                        'version': version,
                    }]
                })
            except Exception:
                retries -= 1
                if not retries:
                    self.logger.error('Failed to send firstboot statistics', exc_info=True)
            else:
                break

