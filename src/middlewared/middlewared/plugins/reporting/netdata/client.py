import aiohttp
import aiohttp.client_exceptions
import asyncio
import contextlib
import json

from .exceptions import ApiException, ClientConnectError
from .utils import NETDATA_URI, NETDATA_REQUEST_TIMEOUT


class ClientMixin:

    @classmethod
    @contextlib.asynccontextmanager
    async def request(
        cls, resource: str, timeout: int = NETDATA_REQUEST_TIMEOUT, version: str = 'v1',
    ) -> aiohttp.ClientResponse:
        assert version in ('v1', 'v2'), f'Invalid API version {version!r}'

        resource = resource.removeprefix('/')
        uri = f'{NETDATA_URI}/{version}/{resource}'
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get(uri) as resp:
                    if resp.status != 200:
                        raise ApiException(f'Received {resp.status!r} response code from {uri!r}')

                    yield resp
        except (asyncio.TimeoutError, aiohttp.ClientResponseError) as e:
            raise ApiException(f'Failed {resource!r} call: {e!r}')
        except (aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ClientOSError) as e:
            raise ClientConnectError(f'Failed to connect to {uri!r}: {e!r}')

    @classmethod
    async def api_call(cls, resource: str, timeout: int = NETDATA_REQUEST_TIMEOUT, version: str = 'v1') -> dict:
        try:
            async with cls.request(resource, timeout, version) as resp:
                output = ''
                async for line in resp.content.iter_any():
                    output += line.decode(errors='ignore')
                return json.loads(output)
        except aiohttp.client_exceptions.ContentTypeError as e:
            raise ApiException(f'Malformed response received from {resource!r} endpoint: {e}')
