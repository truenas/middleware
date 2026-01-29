import asyncio

import aiohttp

from middlewared.utils import ajson


class TruecommandAPIMixin:

    PORTAL_URI = 'https://portal.ixsystems.com/api'

    async def _post_call(self, options=None, payload=None):
        if not await self.middleware.call('network.general.can_perform_activity', 'truecommand'):
            return {'error': 'Network activity denied for TrueCommand service'}

        options = options or {}
        timeout = options.get('timeout', 15)
        response = {'error': None, 'response': {}}
        if not payload:
            data = {}
        else:
            data = await ajson.dumps(payload)

        try:
            async with asyncio.timeout(timeout):
                async with aiohttp.ClientSession(
                    raise_for_status=True, trust_env=True,
                ) as session:
                    req = await session.post(
                        self.PORTAL_URI, data=data, headers={'Content-type': 'application/json'},
                    )
        except asyncio.TimeoutError:
            response['error'] = f'Unable to connect with iX portal in {timeout} seconds.'
        except aiohttp.ClientResponseError as e:
            response['error'] = f'Error Code ({req.status}): {e}'
        else:
            response['response'] = await req.json()
        return response


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'truecommand', 'TrueCommand iX portal')
