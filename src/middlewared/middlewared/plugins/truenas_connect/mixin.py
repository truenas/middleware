import asyncio
import json

import aiohttp

from middlewared.service import private


def auth_headers(config: dict) -> dict:
    return {'Authorization': f'Bearer {config["jwt_token"]}'}


class TNCAPIMixin:

    @private
    async def auth_headers(self, config: dict) -> dict:
        return auth_headers(config)

    async def _call(
        self, endpoint: str, mode: str, *, options: dict | None = None, payload: dict | None = None,
        headers: dict | None = None, json_response: bool = True, get_response: bool = True,
    ):
        # FIXME: Add network activity check for TNC
        options = options or {}
        timeout = options.get('timeout', 15)
        response = {
            'error': None,
            'response': {},
            'status_code': None,
        }
        if payload and (headers is None or 'Content-Type' not in headers):
            headers = headers or {}
            headers['Content-Type'] = 'application/json'
        try:
            async with asyncio.timeout(timeout):
                async with aiohttp.ClientSession(raise_for_status=True, trust_env=True) as session:
                    req = await getattr(session, mode)(
                        endpoint,
                        data=json.dumps(payload) if payload else payload,
                        headers=headers,
                    )
                    response['status_code'] = req.status
        except asyncio.TimeoutError:
            response['error'] = f'Unable to connect with TNC in {timeout} seconds.'
        except aiohttp.ClientResponseError as e:
            response['error'] = str(e)
        except aiohttp.ClientConnectorError as e:
            response['error'] = f'Failed to connect to TNC: {e}'
        else:
            if get_response:
                response['response'] = await req.json() if json_response else await req.text()
        return response
