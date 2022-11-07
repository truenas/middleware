import aiohttp
import aiohttp.client_exceptions
import asyncio
import async_timeout
import urllib.parse

from .config import get_config
from .exceptions import ApiException


class ClientMixin:

    def __init__(self):
        self.config = get_config()

    async def call(self, endpoint, mode, body=None, headers=None, response_type='json', timeout=50):
        try:
            async with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=self.config.ssl_context)
                ) as session:
                    req = await getattr(session, mode)(
                        urllib.parse.urljoin(self.config.server, endpoint), json=body, headers=headers
                    )
        except (asyncio.TimeoutError, aiohttp.ClientResponseError) as e:
            raise ApiException(f'Failed {endpoint!r} call: {e!r}')
        else:
            if req.status != 200:
                raise ApiException(f'Received {req.status!r} response code from {endpoint!r}')

            try:
                return await req.json() if response_type == 'json' else await req.text()
            except aiohttp.client_exceptions.ContentTypeError as e:
                raise ApiException(f'Malformed response received from {endpoint!r} endpoint')
            except asyncio.TimeoutError:
                raise ApiException(f'Timed out waiting for response from {endpoint!r}')
