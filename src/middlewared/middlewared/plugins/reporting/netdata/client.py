import typing

import aiohttp
import aiohttp.client_exceptions
import asyncio
import contextlib
import logging

from middlewared.utils.ajson import json

from .exceptions import ApiException, ClientConnectError
from .utils import NETDATA_URI, NETDATA_REQUEST_TIMEOUT


logger = logging.getLogger('netdata_api')


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
                # our incessant desire to make everything async bites us in
                # scenarios like this if the developer isn't careful. There
                # is potential the `output` variable is a HUGE string. The
                # json.loads/dumps methods are NOT async safe (at time of writing).
                # So on _LARGE_ strings that need to be decoded, this means
                # the main event loop "not responding" or "lagging" becomes
                # measurable.
                return await json.loads(output)
        except aiohttp.client_exceptions.ContentTypeError as e:
            raise ApiException(f'Malformed response received from {resource!r} endpoint: {e}')

    @classmethod
    async def fetch(cls, uri: str, session: aiohttp.ClientSession, identifier: typing.Optional[str]) -> dict:
        output = ''
        response = {'error': None, 'data': None, 'uri': uri, 'identifier': identifier}
        async with session.get(uri) as call_resp:
            if call_resp.status != 200:
                response['error'] = f'Received {call_resp.status!r} response code from {uri!r}'
            else:
                try:
                    async for line in call_resp.content.iter_any():
                        output += line.decode(errors='ignore')
                    response['data'] = await json.loads(output)
                except aiohttp.client_exceptions.ContentTypeError as e:
                    response['error'] = f'Malformed response received from {uri!r} endpoint: {e}'
                except json.JSONDecodeError:
                    response['error'] = f'Failed to decode response from {uri!r}'

        return response

    @classmethod
    @contextlib.asynccontextmanager
    async def multiple_requests(
        cls, resources: typing.List[typing.Tuple[str, str]], timeout: int = NETDATA_REQUEST_TIMEOUT, version: str = 'v1'
    ) -> typing.List[dict]:
        assert version in ('v1', 'v2'), f'Invalid API version {version!r}'

        uri = f'{NETDATA_URI}/{version}'
        tasks = []
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                for identifier, resource in resources:
                    resource = resource.removeprefix('/')
                    tasks.append(cls.fetch(f'{uri}/{resource}', session, identifier))

                yield await asyncio.gather(*tasks)

        except (asyncio.TimeoutError, aiohttp.ClientResponseError) as e:
            raise ApiException(f'Failed {resources!r} call: {e!r}')
        except (aiohttp.client_exceptions.ClientConnectorError, aiohttp.client_exceptions.ClientOSError) as e:
            raise ClientConnectError(f'Failed to connect to {uri!r}: {e!r}')

    @classmethod
    async def api_calls(
        cls, resources: typing.List[typing.Tuple[str, str]], timeout: int = NETDATA_REQUEST_TIMEOUT, version: str = 'v1'
    ) -> typing.List[typing.Tuple[typing.Optional[str], dict]]:
        responses = []
        try:
            async with cls.multiple_requests(resources, timeout, version) as tasks:
                for task in tasks:
                    if task['error']:
                        responses.append((task['identifier'], {
                            'labels': ['time'],
                            'data': [],
                        }))
                    else:
                        responses.append((task['identifier'], task['data']))
        except Exception as e:
            logger.debug('Failed to connect to netdata: %s', e)

        return responses
