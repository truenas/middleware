import aiohttp
import json
import os

from middlewared.service import Service


class UsageService(Service):

    FAILED_RETRIES = 3

    class Config:
        private = True

    async def submit_stats(self, data):
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            await session.post(
                'https://usage.freenas.org/submit',
                data=data,
                headers={'Content-type': 'application/json'},
                proxy=os.environ.get('http_proxy'),
            )

    async def firstboot(self):
        hash = await self.middleware.call('usage.retrieve_system_hash')
        version = (await self.middleware.call('usage.gather_system_version', {}))['version']
        retries = self.FAILED_RETRIES

        while retries:
            try:
                await self.submit_stats(json.dumps({
                    'platform': 'TrueNAS-SCALE',
                    'system_hash': hash,
                    'firstboot': [{
                        'version': version,
                    }]
                }))
            except Exception:
                retries -= 1
                if not retries:
                    self.logger.error('Failed to send firstboot statistics', exc_info=True)
            else:
                break

