import asyncio
import json

import aiohttp
import async_timeout


class TNCAPIMixin:

    async def auth_headers(self, config: dict) -> dict:
        return {'Authorization': f'Bearer {config["jwt_token"]}'}

    async def _call(
        self, endpoint: str, mode: str, *, options: dict | None = None, payload: dict | None = None,
        headers: dict | None = None,
    ):
        # FIXME: Add network activity check for TNC
        options = options or {}
        timeout = options.get('timeout', 15)
        response = {'error': None, 'response': {}}
        try:
            async with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(raise_for_status=True, trust_env=True) as session:
                    req = await getattr(session, mode)(
                        endpoint,
                        data=json.dumps(payload) if payload else payload,
                        headers=headers,
                    )
        except asyncio.TimeoutError:
            response['error'] = f'Unable to connect with TNC in {timeout} seconds.'
        except aiohttp.ClientResponseError as e:
            response['error'] = f'Error Code ({req.status}): {e}'
        else:
            response['response'] = await req.json()
        return response
