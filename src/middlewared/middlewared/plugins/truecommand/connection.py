import aiohttp
import async_timeout
import asyncio
import os
import json


class TruecommandAPIMixin:

    PORTAL_URI = 'https://portal.ixsystems.com/api'

    async def _post_call(self, options=None, payload=None):
        options = options or {}
        timeout = options.get('timeout', 15)
        response = {'error': None, 'response': {}}
        try:
            with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(
                    raise_for_status=True
                ) as session:
                    req = await session.post(
                        'https://usage.freenas.org/submit',
                        data=json.dumps(payload or {}),
                        headers={'Content-type': 'application/json'},
                        proxy=os.environ.get('http_proxy'),
                    )
        except asyncio.TimeoutError:
            response['error'] = f'Unable to connect with iX portal in {timeout} seconds.'
        except aiohttp.ClientResponseError as e:
            response['error'] = f'Error Code ({req.status}): {e}'
        else:
            response['response'] = req.json()
        return response
